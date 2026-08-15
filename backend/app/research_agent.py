"""Persistent multi-round research orchestration over existing collectors."""
from __future__ import annotations

import asyncio
import logging
import json
from urllib.parse import urlparse
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.engine import CollectionEngine
from app.models import CollectedItem, ModelConfig, ResearchJob, ResearchRound, SourceConfig, Topic
from app.model_defaults import get_default_model
from app.case_entity_research import build_gap_followups, enrich_entities_with_llm, update_cross_source_verification
from app.research_acceptance import acceptance_followups, evaluate_acceptance
from app.research_graph import sync_research_graph

logger = logging.getLogger(__name__)
_tasks: dict[str, asyncio.Task] = {}


def utcnow():
    return datetime.now(timezone.utc)


def create_job(db: Session, *, topic_id: str, objective: str, model_id: str | None,
               max_rounds: int, target_items: int, acceptance_policy: dict | None = None) -> ResearchJob:
    if not db.get(Topic, topic_id):
        raise ValueError(f"Topic not found: {topic_id}")
    job = ResearchJob(
        id=f"research-{uuid4().hex[:12]}", topic_id=topic_id,
        objective=objective.strip(), model_id=model_id, max_rounds=max_rounds,
        target_items=target_items, acceptance_policy={"min_items": target_items, **(acceptance_policy or {})}, status="pending", run_ids=[],
        result_item_ids=[], progress=[{"stage": "queued", "message": "任务已进入研究队列"}],
    )
    db.add(job); db.commit(); db.refresh(job)
    return job


def start_job(job_id: str) -> None:
    task = _tasks.get(job_id)
    if task and not task.done():
        return
    _tasks[job_id] = asyncio.create_task(run_job(job_id))


def _research_sources(db: Session, topic: Topic) -> list[str]:
    configured = set(topic.source_ids or [])
    rows = db.query(SourceConfig).filter(SourceConfig.is_active == True).all()
    is_research = lambda row: getattr(row.channel, "value", row.channel) == "ai_research"
    preferred = [row.id for row in rows if row.id in configured and is_research(row)]
    if preferred:
        return preferred
    return [row.id for row in rows if is_research(row)][:1]


async def run_job(job_id: str) -> None:
    db = SessionLocal()
    try:
        job = db.get(ResearchJob, job_id)
        if not job:
            return
        job.status, job.started_at = "running", utcnow()
        db.commit()
        topic = db.get(Topic, job.topic_id)
        research_model = db.get(ModelConfig, job.model_id) if job.model_id else get_default_model(db)
        source_ids = _research_sources(db, topic)
        if not source_ids:
            raise RuntimeError("没有启用的 AI 智能检索信息源")

        accumulated: list[str] = list(job.result_item_ids or [])
        all_runs: list[str] = list(job.run_ids or [])
        previous_titles: list[str] = []
        followup_queries: list[str] = []
        start_round = max(1, int(job.current_round or 0) + 1)
        for number in range(start_round, job.max_rounds + 1):
            job.current_round = number
            progress = list(job.progress or [])
            progress.append({"stage": "round", "round": number, "message": f"开始第 {number}/{job.max_rounds} 轮检索"})
            job.progress = progress
            round_prompt = (
                f"研究目标：{job.objective}\n"
                f"这是第{number}轮，共{job.max_rounds}轮。必须搜索公开原文并保留URL、发布日期和证据。"
                "区分已证实事实与分析推断，优先独立正文、官方来源和交叉验证。"
                f"上一轮已发现标题：{'；'.join(previous_titles[-12:]) or '无'}。"
                "本轮避免重复，补足主体、时间、地点、货物/产品、路线、单证和可执行核查建议。"
            )
            if followup_queries:
                round_prompt += "\n[FOLLOWUP_QUERIES] " + json.dumps(followup_queries, ensure_ascii=False)
            rr = ResearchRound(id=f"{job.id}-r{number}", job_id=job.id, round_number=number,
                               prompt=round_prompt, status="running", started_at=utcnow())
            db.add(rr); db.commit()
            before = {row.id for row in db.query(CollectedItem.id).filter(CollectedItem.topic_id == topic.id)}
            try:
                results = await asyncio.wait_for(
                    CollectionEngine(db).collect_topic(
                        topic.id, research_prompt=round_prompt,
                        research_model_id=job.model_id, only_source_ids=source_ids,
                    ),
                    timeout=600,
                )
            except TimeoutError as exc:
                rr.status, rr.error_log, rr.completed_at = "failed", "本轮外部检索超过 10 分钟", utcnow()
                db.commit()
                raise RuntimeError(rr.error_log) from exc
            run_ids = [r.run_id for r in results if r.run_id]
            rows = db.query(CollectedItem).filter(CollectedItem.run_id.in_(run_ids)).all() if run_ids else []
            new_rows = [row for row in rows if row.id not in before]
            for row in new_rows:
                if row.id not in accumulated:
                    accumulated.append(row.id)
                await enrich_entities_with_llm(row, research_model)
            # A research job is a portfolio over a time window, not merely a
            # count of newly inserted rows. Reuse previously approved cases in
            # the same window so deduplication does not make repeat research
            # falsely report zero evidence.
            window_rows = db.query(CollectedItem).filter(
                CollectedItem.topic_id == topic.id,
                CollectedItem.published_at >= datetime.combine(
                    (utcnow().date() - timedelta(days=max(1, int(topic.collect_window_days or 7)) - 1)),
                    datetime.min.time(), tzinfo=timezone.utc,
                ),
            ).all()
            for row in window_rows:
                if _is_reusable_case(row) and row.id not in accumulated:
                    accumulated.append(row.id)
            previous_titles = [row.title for row in rows]
            accumulated_rows = db.query(CollectedItem).filter(CollectedItem.id.in_(accumulated)).all() if accumulated else []
            update_cross_source_verification(accumulated_rows)
            today = utcnow().date()
            start = today - timedelta(days=max(1, int(topic.collect_window_days or 7)) - 1)
            followup_queries = build_gap_followups(
                accumulated_rows, window_start=start.isoformat(), window_end=today.isoformat(),
            )
            sync_research_graph(db, accumulated_rows)
            acceptance = evaluate_acceptance(accumulated_rows, job.acceptance_policy)
            job.acceptance_result = acceptance
            followup_queries = list(dict.fromkeys([
                *acceptance_followups(acceptance, start.isoformat(), today.isoformat()),
                *followup_queries,
            ]))[:32]
            if {"strong_china_ratio", "china_ratio"} & set(acceptance.get("gaps") or []):
                # Until the China quota is satisfied, spend every subsequent
                # search slot on explicit China evidence and entity follow-up.
                followup_queries = [query for query in followup_queries if any(
                    marker in query.casefold() for marker in (
                        "china", "chinese", "shanghai", "ningbo", "shenzhen",
                        "yantian", "qingdao", "xiamen", "hong kong", "中国", "中國",
                    )
                )][:32]
            all_runs.extend(run_ids)
            rr.run_ids, rr.item_ids, rr.items_new = run_ids, [row.id for row in rows], len(new_rows)
            rr.status, rr.completed_at = "completed", utcnow()
            job.run_ids, job.result_item_ids = all_runs, accumulated
            progress = list(job.progress or [])
            progress.append({"stage": "round_completed", "round": number, "items_new": len(new_rows), "total": len(accumulated), "followup_queries": len(followup_queries)})
            job.progress = progress
            db.commit()
            if acceptance["passed"]:
                break

        job.status, job.completed_at = "completed", utcnow()
        job.progress = [*(job.progress or []), {"stage": "completed", "message": f"研究完成，共形成 {len(accumulated)} 条审核后证据", "acceptance_passed": bool((job.acceptance_result or {}).get("passed"))}]
        db.commit()
    except Exception as exc:
        logger.exception("Research job %s failed", job_id)
        db.rollback()
        job = db.get(ResearchJob, job_id)
        if job:
            job.status, job.error_log, job.completed_at = "failed", str(exc), utcnow()
            db.commit()
    finally:
        db.close()
        _tasks.pop(job_id, None)


def _is_reusable_case(item: CollectedItem) -> bool:
    review = (item.raw_metadata or {}).get("enforcement_review") or {}
    if review.get("decision", "approve") != "approve":
        return False
    title = (item.title or "").casefold()
    path = urlparse(item.url or "").path.casefold().rstrip("/")
    listing_markers = ("homepage", "latest news", "keyword news", "關鍵字新聞", "关键词新闻")
    if any(marker in title for marker in listing_markers):
        return False
    return path not in {"", "/news", "/newsroom", "/tag", "/search"}
