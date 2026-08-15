"""
Collection Engine — the central orchestrator.

Flow:
    Topic → keywords → sources → connectors → FetchItems
    → dedup → persist (with topic_id) → auto-tag → return stats
"""
import asyncio
import logging
import re
from collections import Counter
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.connectors.base import ConnectorRegistry, CollectResult, FetchItem
from app.content_parser import parse_fetch_item
from app.model_defaults import get_default_model
from app.models import (
    CollectionRun, CollectedItem, ItemStatus,
    JobStatus, ModelConfig, SourceConfig, Tag, Topic,
)

logger = logging.getLogger(__name__)
_translation_lock = asyncio.Lock()
SEMANTIC_SEARCH_CHANNELS = frozenset({"ai_research", "api_search"})
MAX_PROGRESS_EVENTS = 120
MAX_ITEM_PROGRESS_EVENTS = 40
MAX_CANDIDATES_PER_SOURCE = 9
MAX_ENFORCEMENT_CANDIDATES_PER_SOURCE = 45
MAX_ENFORCEMENT_SEARCH_RESULTS_PER_SOURCE = 120
SOURCE_COLLECTION_CONCURRENCY = 4
SOURCE_EXECUTION_TIMEOUT_SECONDS = 90
SEMANTIC_SOURCE_EXECUTION_TIMEOUT_SECONDS = 600
ENFORCEMENT_DISCOVERY_KEYWORDS = (
    "seiz", "intercept", "apprehend", "arrest", "charg", "detain",
    "confiscat", "contraband", "counterfeit", "undeclared", "unreported",
    "illegal import", "illegal export", "drug", "fentanyl", "cocaine",
    "methamphetamine", "weapon", "firearm", "tobacco", "wildlife",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _topic_collection_keywords(topic: Topic) -> list[str]:
    values = topic.keywords if isinstance(topic.keywords, list) else [topic.keywords]
    keywords = [str(value).strip() for value in values if str(value or "").strip()]
    if topic.id != "weekly-enforcement-intelligence":
        return keywords

    seen = {keyword.casefold() for keyword in keywords}
    for keyword in ENFORCEMENT_DISCOVERY_KEYWORDS:
        if keyword.casefold() not in seen:
            keywords.append(keyword)
            seen.add(keyword.casefold())
    return keywords


def _topic_collection_prompt(db: Session, topic: Topic, override: str | None = None) -> str:
    """Combine the run override, topic instruction, and enabled reusable prompts."""
    from app.models import PromptTemplate

    sections = [value.strip() for value in [override, topic.description_prompt] if value and value.strip()]
    prompt_ids = topic.prompt_template_ids if isinstance(topic.prompt_template_ids, list) else []
    if prompt_ids:
        templates = db.query(PromptTemplate).filter(
            PromptTemplate.id.in_(prompt_ids), PromptTemplate.is_active == True,
        ).all()
        by_id = {template.id: template for template in templates}
        sections.extend(
            f"【挂载提示词：{by_id[prompt_id].name}】\n{by_id[prompt_id].content.strip()}"
            for prompt_id in prompt_ids
            if prompt_id in by_id and by_id[prompt_id].content.strip()
        )
    return "\n\n".join(dict.fromkeys(sections))


async def _translate_persisted_items(item_ids: list[str], model_id: str | None) -> dict:
    """Translate persisted items before collection results are exposed to the UI."""
    from app.database import SessionLocal
    from app.translation_service import translate_existing_items

    # A local model cannot reliably serve several long translation batches at once.
    # Serialize post-collection translations so later sources wait instead of failing.
    async with _translation_lock:
        db = SessionLocal()
        try:
            model = (
                db.query(ModelConfig).filter(ModelConfig.id == model_id).first()
                if model_id else get_default_model(db) or _web_translation_model()
            )
            if model:
                return await translate_existing_items(
                    db, model, limit=len(item_ids), item_ids=item_ids,
                )
            return {"requested": len(item_ids), "translated": 0, "items": []}
        except Exception as exc:
            logger.warning("Background item translation failed: %s", exc)
            return {
                "requested": len(item_ids), "translated": 0,
                "items": [], "errors": [str(exc)],
            }
        finally:
            db.close()


class CollectionEngine:
    def __init__(self, db: Session):
        self.db = db

    def _record_progress(
        self,
        run: CollectionRun,
        stage: str,
        message: str,
        *,
        status: str = "running",
        item_title: str | None = None,
        detail: dict | None = None,
        commit: bool = True,
    ) -> None:
        event = {
            "stage": stage,
            "status": status,
            "message": message,
            "item_title": item_title,
            "detail": dict(detail or {}),
            "created_at": utc_now().isoformat(),
        }
        previous = [dict(entry) for entry in (run.progress_events or []) if isinstance(entry, dict)]
        run.progress_events = [*previous, event][-MAX_PROGRESS_EVENTS:]
        if commit:
            self.db.commit()

    # ── Single source collection ────────────────────────────────────────

    async def collect_from_source(
        self, source_id: str, keywords: list[str], topic_id: str | None = None,
        window_start: "datetime | None" = None, window_end: "datetime | None" = None,
        batch_id: str | None = None, model: ModelConfig | None = None,
        semantic_prompt: str | None = None,
    ) -> CollectResult:
        """Collect from one source with given keywords.

        When window_start is provided, items outside the window are skipped.
        Undated items are kept only if a usable date can be extracted from text.
        """
        source = self.db.query(SourceConfig).filter(SourceConfig.id == source_id).first()
        if not source:
            raise ValueError(f"Source not found: {source_id}")
        if not source.is_active:
            return CollectResult(
                run_id="", source_id=source_id, status=JobStatus.FAILED,
                items=[], error_log=["Source is not active"],
            )

        run = CollectionRun(
            id=f"run-{uuid4().hex[:12]}",
            source_id=source.id,
            topic_id=topic_id,
            job_id=f"job-{uuid4().hex[:8]}",
            status=JobStatus.PENDING,
            keywords_used=keywords,
            window_start=window_start,
            window_end=window_end,
        )
        run.batch_id = batch_id
        run.status = JobStatus.RUNNING
        run.started_at = utc_now()
        self.db.add(run)
        self.db.commit()
        self._record_progress(
            run, "queued", f"已创建采集任务，准备连接信息源“{source.name}”",
            detail={"source_id": source.id, "source_name": source.name},
        )

        try:
            self._record_progress(
                run, "connecting", f"正在连接信息源“{source.name}”",
                detail={"source_id": source.id, "source_name": source.name},
            )
            connector = ConnectorRegistry.create(source)
            connector.set_collection_window(window_start, window_end)
        except ValueError as exc:
            run.status = JobStatus.FAILED
            run.error_log = [str(exc)]
            self._record_progress(
                run, "failed", f"信息源连接失败：{exc}", status="failed",
            )
            return CollectResult(run_id=run.id, source_id=source.id,
                                 status=JobStatus.FAILED, items=[], error_log=[str(exc)])

        self._record_progress(
            run, "searching", f"正在“{source.name}”检索与主题相关的信息",
            detail={"query_count": len(keywords)},
        )
        execution_timeout = (
            SEMANTIC_SOURCE_EXECUTION_TIMEOUT_SECONDS
            if _channel_value(source) in SEMANTIC_SEARCH_CHANNELS
            else SOURCE_EXECUTION_TIMEOUT_SECONDS
        )
        try:
            runtime_max_items = (
                max(source.max_items_per_run or 0, MAX_ENFORCEMENT_SEARCH_RESULTS_PER_SOURCE)
                if topic_id == "weekly-enforcement-intelligence"
                and _channel_value(source) in SEMANTIC_SEARCH_CHANNELS
                else None
            )
            result = await asyncio.wait_for(
                connector.execute(run, keywords, max_items=runtime_max_items),
                timeout=execution_timeout,
            )
        except TimeoutError:
            message = f"信息源处理超过 {execution_timeout} 秒，已停止以保护采集队列"
            run.status = JobStatus.FAILED
            run.completed_at = utc_now()
            run.error_log = [message]
            self._record_progress(run, "failed", message, status="failed")
            return CollectResult(
                run_id=run.id, source_id=source.id, status=JobStatus.FAILED,
                items=[], error_log=[message],
            )
        if result.status == JobStatus.FAILED:
            self._record_progress(
                run, "failed", f"信息源采集失败：{'；'.join(result.error_log or ['未知错误'])}",
                status="failed",
            )
            return result

        run.status = JobStatus.RUNNING
        run.completed_at = None
        run.items_found = len(result.items)
        self._record_progress(
            run, "fetched", f"信息源返回 {len(result.items)} 条候选信息，正在逐条核验",
            detail={"items_found": len(result.items)},
        )
        for item in result.items[:MAX_ITEM_PROGRESS_EVENTS]:
            self._record_progress(
                run, "discovered", f"发现候选信息：《{item.title or '未命名信息'}》",
                item_title=item.title or None,
                detail={"url": item.url or "", "published_at": str(item.published_at or "")},
                commit=False,
            )
        self.db.commit()

        window_items, window_rejected = _filter_items_by_window(
            result.items, window_start, window_end
        )
        existing_skipped = 0
        if topic_id == "weekly-enforcement-intelligence":
            window_items, existing_skipped = (
                self._exclude_existing_enforcement_candidates(window_items)
            )
            if existing_skipped:
                self._record_progress(
                    run,
                    "deduplicated",
                    f"审核前已排除 {existing_skipped} 条数据库已有案例，避免重复占用模型额度",
                    detail={"existing_skipped": existing_skipped},
                )
        if topic_id == "weekly-enforcement-intelligence":
            from app.enforcement_review import prioritize_enforcement_candidates
            existing_counts = self._enforcement_jurisdiction_counts(window_start)
            # The library is cumulative. Existing items should influence
            # geographic ordering, but must never close the review gate for a
            # later collection run.
            candidate_limit = MAX_ENFORCEMENT_CANDIDATES_PER_SOURCE
            retained_items = prioritize_enforcement_candidates(
                window_items,
                candidate_limit,
                existing_counts=existing_counts,
            )
        else:
            candidate_limit = MAX_CANDIDATES_PER_SOURCE
            retained_items = window_items[:candidate_limit]
        candidate_limited = max(0, len(window_items) - len(retained_items))
        result.items = retained_items
        result.items_failed += window_rejected + candidate_limited
        if window_rejected:
            result.error_log = [
                *(result.error_log or []),
                f"采集窗口过滤 {window_rejected} 条：发布日期缺失或超出范围",
            ]
        if candidate_limited:
            result.error_log = [
                *(result.error_log or []),
                f"候选限额保留 {len(retained_items)} 条，延后处理 {candidate_limited} 条",
            ]
        self._record_progress(
            run, "window_review",
            f"时间窗口与候选限额核验完成：保留 {len(retained_items)} 条，排除或延后 {window_rejected + candidate_limited} 条",
            detail={"kept": len(retained_items), "rejected": window_rejected, "deferred": candidate_limited},
        )
        if topic_id == "weekly-enforcement-intelligence" and result.items:
            self._record_progress(
                run,
                "hydrating",
                f"正在并发读取 {len(result.items)} 个候选原网页，补充执法事实和来源证据",
            )
            result.items = await _hydrate_enforcement_candidates(result.items)
        if model is None:
            model = get_default_model(self.db)

        # A search result is only a lead. Before it reaches the local library,
        # reject listing/advertising pages and use the selected model to turn a
        # complete article into a concise Chinese intelligence brief.
        from app.content_quality import curate_article_candidates
        topic = (
            self.db.query(Topic).filter(Topic.id == topic_id).first()
            if topic_id else None
        )
        self._record_progress(
            run, "quality_review", f"正在对 {len(result.items)} 条信息进行价值、独立性和完整性审核",
        )
        if topic_id == "weekly-enforcement-intelligence":
            # The dedicated evidence gate below is authoritative for concise
            # official enforcement releases and search-result leads.
            approved_items = result.items
            rejected_items = []
        else:
            approved_items, rejected_items = await curate_article_candidates(
                result.items,
                model,
                _topic_review_context(topic, semantic_prompt) if topic else None,
            )
        result.items = approved_items
        result.items_failed += len(rejected_items)
        if rejected_items:
            reasons = list(dict.fromkeys(rejection.reason for rejection in rejected_items))
            result.error_log = [*(result.error_log or []), f"质量审核拒绝 {len(rejected_items)} 条：{'；'.join(reasons[:3])}"]
        for rejection in rejected_items[:MAX_ITEM_PROGRESS_EVENTS]:
            self._record_progress(
                run, "rejected", f"未纳入：《{rejection.item.title or '未命名信息'}》；{rejection.reason}",
                status="skipped", item_title=rejection.item.title or None,
                detail={"reason": rejection.reason, "url": rejection.item.url or ""},
                commit=False,
            )
        for item in approved_items[:MAX_ITEM_PROGRESS_EVENTS]:
            self._record_progress(
                run,
                "quality_approved",
                f"基础质量检查通过，等待执法语义审核：《{item.title or '未命名信息'}》",
                item_title=item.title or None,
                detail={"url": item.url or ""}, commit=False,
            )
        self.db.commit()

        if topic_id == "weekly-enforcement-intelligence":
            from app.enforcement_review import review_enforcement_candidates
            # Keep manual/topic source runs on the same review path. Some
            # callers do not pass a model explicitly, so resolve the active
            # default here instead of silently queueing everything pending.
            if model is None or not model.is_active or not model.api_key:
                model = get_default_model(self.db)
            result.items = await review_enforcement_candidates(result.items, model)
            for item in result.items[:MAX_ITEM_PROGRESS_EVENTS]:
                review = (
                    (item.raw_metadata or {}).get("enforcement_review", {})
                    if isinstance(item.raw_metadata, dict) else {}
                )
                self._record_progress(
                    run,
                    "semantic_approved",
                    f"执法语义审核通过：《{item.title or '未命名信息'}》",
                    item_title=item.title or None,
                    detail={
                        "url": item.url or "",
                        "jurisdiction": review.get("jurisdiction"),
                        "case_type": review.get("case_type"),
                    },
                    commit=False,
                )
            self.db.commit()
            result.items, portfolio_skipped = self._select_enforcement_portfolio(
                result.items, window_start,
            )
            if portfolio_skipped:
                result.items_failed += portfolio_skipped
                result.error_log = [
                    *(result.error_log or []),
                    f"30天案例组合控制跳过 {portfolio_skipped} 条：优先补足低覆盖国家地区并限制单一地区集中",
                ]
            result.items_new = len(result.items)
            run.items_new = result.items_new
        persisted_count = self._persist_items(
            result.items, source.id, run.id, topic_id, window_start, window_end, keywords
        )
        result.items_new = persisted_count
        run.items_new = persisted_count
        duplicate_count = max(0, len(result.items) - persisted_count)
        self._record_progress(
            run, "persisted",
            f"已入库 {persisted_count} 条新信息，识别并跳过 {duplicate_count} 条重复或已存在信息",
            detail={"items_new": persisted_count, "duplicates_or_existing": duplicate_count},
        )
        self._update_source(source, persisted_count)
        self.db.commit()
        if result.items:
            item_ids = [item.item_id(source.id) for item in result.items]
            self._record_progress(
                run, "translating", f"正在翻译并整理 {len(item_ids)} 条信息的中文标题、摘要和正文",
            )
            translation = await _translate_persisted_items(item_ids, model.id if model else None)
            translated_ids = set(translation.get("items", []))
            for item in result.items[:MAX_ITEM_PROGRESS_EVENTS]:
                item_id = item.item_id(source.id)
                action = "中文转译与内容整理完成" if item_id in translated_ids else "中文内容整理完成"
                self._record_progress(
                    run, "translated", f"{action}：《{item.title or '未命名信息'}》",
                    item_title=item.title or None,
                    detail={"item_id": item_id, "url": item.url or ""}, commit=False,
                )
            self.db.commit()
        run.status = result.status
        run.completed_at = utc_now()
        if run.started_at:
            started_at = run.started_at
            if started_at.tzinfo is None:
                started_at = started_at.replace(tzinfo=timezone.utc)
            run.duration_ms = int((run.completed_at - started_at).total_seconds() * 1000)
        self._record_progress(
            run, "completed", f"采集处理完成，共新增 {persisted_count} 条有效信息",
            status="completed", detail={"items_new": persisted_count},
        )
        return result

    def _exclude_existing_enforcement_candidates(
        self, items: list[FetchItem],
    ) -> tuple[list[FetchItem], int]:
        """Remove known cases before costly model review."""
        existing = self.db.query(
            CollectedItem.url,
            CollectedItem.title,
            CollectedItem.content,
        ).filter(
            CollectedItem.topic_id == "weekly-enforcement-intelligence",
        ).all()
        existing_keys = {
            _dedupe_fingerprint(row.url, row.title or "", row.content)
            for row in existing
        }
        retained: list[FetchItem] = []
        seen: set[str] = set()
        for item in items:
            key = _dedupe_fingerprint(item.url, item.title, item.content)
            if key in existing_keys or key in seen:
                continue
            seen.add(key)
            retained.append(item)
        return retained, len(items) - len(retained)

    def _enforcement_jurisdiction_counts(
        self, window_start: datetime | None,
    ) -> Counter[str]:
        from app.enforcement_review import infer_enforcement_jurisdiction

        query = self.db.query(CollectedItem).filter(
            CollectedItem.topic_id == "weekly-enforcement-intelligence",
        )
        if window_start is not None:
            query = query.filter(CollectedItem.published_at >= window_start)
        counts: Counter[str] = Counter()
        for stored in query.all():
            metadata = (
                stored.raw_metadata
                if isinstance(stored.raw_metadata, dict)
                else {}
            )
            counts[infer_enforcement_jurisdiction(FetchItem(
                title=stored.title,
                content=stored.content,
                summary=stored.summary,
                url=stored.url,
                raw_metadata=metadata,
            ))] += 1
        return counts

    def _backfill_enforcement_metadata(self) -> int:
        from app.enforcement_review import enrich_enforcement_review_metadata

        changed = 0
        items = self.db.query(CollectedItem).filter(
            CollectedItem.topic_id == "weekly-enforcement-intelligence",
        ).all()
        for stored in items:
            metadata = (
                dict(stored.raw_metadata)
                if isinstance(stored.raw_metadata, dict)
                else {}
            )
            enriched = enrich_enforcement_review_metadata(FetchItem(
                title=stored.title,
                content=stored.content,
                summary=stored.summary,
                url=stored.url,
                raw_metadata=metadata,
            ))
            if enriched is None or enriched == metadata.get("enforcement_review"):
                continue
            metadata["enforcement_review"] = enriched
            stored.raw_metadata = metadata
            changed += 1
        if changed:
            self.db.commit()
        return changed

    # ── Topic-driven collection ─────────────────────────────────────────

    async def collect_topic(
        self,
        topic_id: str,
        research_prompt: str | None = None,
        research_model_id: str | None = None,
        only_source_ids: list[str] | None = None,
    ) -> list[CollectResult]:
        """Collect from all sources relevant to a topic."""
        topic = self.db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            raise ValueError(f"Topic not found: {topic_id}")
        if topic.id == "weekly-enforcement-intelligence":
            self._backfill_enforcement_metadata()

        sources = self._resolve_sources(topic)
        if only_source_ids:
            allowed = set(only_source_ids)
            sources = [source for source in sources if source.id in allowed]
        source_ids = [s.id for s in sources]
        keywords = _topic_collection_keywords(topic)

        # Compute the publication time window from the topic configuration.
        # window_days <= 0 disables filtering (collect everything).
        window_days = getattr(topic, "collect_window_days", None) or 0
        window_end = utc_now()
        if window_days > 0:
            # Weekly reports are date-based. Start at UTC midnight for the
            # boundary date so a valid article published early that day is not
            # lost merely because the job ran later in the day.
            window_start = (window_end - timedelta(days=window_days - 1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            window_start = None

        # Generate a shared batch_id for all runs in this topic collection
        from uuid import uuid4
        batch_id = f"batch-{uuid4().hex[:12]}"

        # Topic-selected models are existing model configs, so no provider
        # credentials need to be copied into a topic. Rotate them by source so
        # multiple selections participate in the collection pipeline.
        default_model = get_default_model(self.db)
        selected_model_ids = topic.collection_model_ids if isinstance(topic.collection_model_ids, list) else []
        collection_models = self.db.query(ModelConfig).filter(
            ModelConfig.id.in_(selected_model_ids),
            ModelConfig.is_active == True,
        ).all() if selected_model_ids else []
        collection_models = [model for model in collection_models if model.model_name]
        research_model = collection_models[0] if collection_models else default_model
        configured_research_model_id = research_model_id or topic.ai_research_model_id
        if configured_research_model_id:
            research_model = self.db.query(ModelConfig).filter(
                ModelConfig.id == configured_research_model_id, ModelConfig.is_active == True
            ).first() or research_model

        semantic_queries: list[str] = []
        effective_research_prompt = _topic_collection_prompt(self.db, topic, research_prompt)
        if any(_channel_value(source) in SEMANTIC_SEARCH_CHANNELS for source in sources):
            try:
                from app.research_planner import build_research_queries
                semantic_queries = await build_research_queries(
                    topic,
                    effective_research_prompt or "",
                    research_model,
                    max_queries=40 if topic.id == "weekly-enforcement-intelligence" else 12,
                    window_days=window_days or 7,
                )
                if semantic_queries:
                    logger.info(
                        "Semantic collection plan generated %d queries for topic %s",
                        len(semantic_queries), topic.id,
                    )
            except Exception as exc:
                logger.warning("AI research prompt planning failed for %s: %s", topic.id, exc)

        # Keep remote sources and SQLite writes within a bounded work queue.
        # A topic may intentionally bind dozens of sources; opening all of them
        # at once makes one slow source starve LLM review and progress updates.
        semaphore = asyncio.Semaphore(SOURCE_COLLECTION_CONCURRENCY)

        async def collect_one(index: int, source: SourceConfig) -> CollectResult:
            async with semaphore:
                return await self.collect_from_source(
                    source.id,
                    semantic_queries if _channel_value(source) in SEMANTIC_SEARCH_CHANNELS and semantic_queries else keywords,
                    topic.id,
                    window_start,
                    window_end,
                    batch_id,
                    collection_models[index % len(collection_models)] if collection_models else default_model,
                    effective_research_prompt,
                )

        tasks = [collect_one(index, source) for index, source in enumerate(sources)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        final: list[CollectResult] = []
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                final.append(CollectResult(
                    run_id="", source_id=source_ids[i] if i < len(source_ids) else "?",
                    status=JobStatus.FAILED, items=[], error_log=[str(r)],
                ))
            else:
                final.append(r)

        # Auto-tag
        if topic.auto_tag_rules:
            self._apply_auto_tags(topic.id, topic.auto_tag_rules)
        self._apply_suggested_tags(topic.id)

        # Update topic
        topic.last_run_at = utc_now()
        topic.total_items_collected += sum(r.items_new for r in final)
        # Track the most recent collection run id (first successful run)
        run_id = next((r.run_id for r in final if getattr(r, "run_id", None)), None)
        if run_id:
            topic.last_collection_run_id = run_id
        self.db.commit()

        # Fire-and-forget notifications after collection (batch aggregation)
        try:
            from app.notification_models import NotificationSender, BatchEvent
            from app.database import SessionLocal
            sender = NotificationSender(SessionLocal)

            # 收集同一批次所有来源的结果，汇总为 BatchEvent 列表
            events: list[BatchEvent] = []
            for r in final:
                source_name = r.source_id
                # 尝试从 source 对象获取友好名称
                try:
                    src = self.db.query(SourceConfig).filter(SourceConfig.id == r.source_id).first()
                    if src and src.name:
                        source_name = src.name
                except Exception:
                    pass
                events.append(BatchEvent(
                    source_id=r.source_id,
                    source_name=source_name,
                    items_new=getattr(r, "items_new", 0) or 0,
                    status="completed" if r.status == JobStatus.COMPLETED else "failed",
                    error=" ".join(r.error_log) if r.error_log else "",
                ))

            sender.send_batch(
                topic_id=topic_id,
                topic_name=topic.name,
                batch_id=batch_id,
                events=events,
            )
        except Exception as exc:
            logger.warning("Notification after collection failed: %s", exc)
        return final

    # ── Scheduled collection ────────────────────────────────────────────

    async def execute_schedule(self, schedule_id: str) -> list[CollectResult]:
        from app.models import ScheduleConfig
        schedule = self.db.query(ScheduleConfig).filter(ScheduleConfig.id == schedule_id).first()
        if not schedule:
            raise ValueError(f"Schedule {schedule_id} not found")

        all_results: list[CollectResult] = []
        for tid in (schedule.topic_ids or []):
            all_results.extend(await self.collect_topic(tid))
        for sid in (schedule.source_ids or []):
            all_results.append(await self.collect_from_source(sid, schedule.keywords or []))

        schedule.last_run_at = utc_now()
        schedule.run_count += 1
        schedule.last_status = (
            JobStatus.FAILED if all(r.status == JobStatus.FAILED for r in all_results)
            else JobStatus.COMPLETED
        )
        self.db.commit()
        return all_results

    # ── Tag system ──────────────────────────────────────────────────────

    def ensure_tag(self, tag_id: str, namespace: str, value: str, label: str | None = None) -> Tag | None:
        from app.services.tag_service import is_valid_tag_value

        if not is_valid_tag_value(value) or (label is not None and not is_valid_tag_value(label)):
            logger.warning("Skipping invalid tag: %r", tag_id)
            return None
        tag = self.db.query(Tag).filter(Tag.id == tag_id).first()
        if not tag:
            tag = Tag(id=tag_id, namespace=namespace, value=value, label=label or value)
            self.db.add(tag)
            self.db.flush()
        tag.last_seen_at = utc_now()
        return tag

    def tag_item(self, item_id: str, tag_id: str) -> bool:
        item = self.db.query(CollectedItem).filter(CollectedItem.id == item_id).first()
        tag = self.db.query(Tag).filter(Tag.id == tag_id).first()
        if not item or not tag:
            return False
        # Use tag_id set comparison to avoid object identity issues
        existing_ids = {t.id for t in item.tags}
        if tag_id not in existing_ids:
            item.tags.append(tag)
            tag.item_count += 1
            if item.status == ItemStatus.RAW:
                item.status = ItemStatus.TAGGED
            return True
        return False

    def _apply_auto_tags(self, topic_id: str, rules: list[dict]) -> int:
        items = self.db.query(CollectedItem).filter(CollectedItem.topic_id == topic_id).all()
        applied = 0
        for item in items:
            text = f"{item.title} {item.content or ''}".lower()
            for rule in rules:
                if rule.get("keyword", "").lower() in text:
                    tag_id = rule.get("tag", "")
                    if tag_id:
                        ns = tag_id.split(":", 1)[0] if ":" in tag_id else "general"
                        val = tag_id.split(":", 1)[1] if ":" in tag_id else tag_id
                        self.ensure_tag(tag_id, ns, val)
                        if self.tag_item(item.id, tag_id):
                            applied += 1
        self.db.commit()
        return applied

    def _apply_suggested_tags(self, topic_id: str):
        items = self.db.query(CollectedItem).filter(
            CollectedItem.topic_id == topic_id,
        ).all()
        for item in items:
            metadata = item.raw_metadata or {}
            # Ingest suggested_tags from Tavily's connector
            suggested = metadata.get("suggested_tags", [])
            if not suggested:
                # Try from the raw Tavily output
                suggested = item.tags_from_metadata()

            # Deduplicate tag IDs while preserving order
            seen: set[str] = set()
            unique_suggested: list[str] = []
            for tag_id in suggested:
                if tag_id and tag_id not in seen:
                    seen.add(tag_id)
                    unique_suggested.append(tag_id)

            for tag_id in unique_suggested:
                parts = tag_id.split(":", 1)
                ns, val = (parts[0], parts[1]) if len(parts) == 2 else ("general", parts[0])
                self.ensure_tag(tag_id, ns, val)
                self.tag_item(item.id, tag_id)

            # Always apply a category tag if item has a category
            if item.category:
                tag_id = f"category:{item.category}"
                self.ensure_tag(tag_id, "category", item.category)
                self.tag_item(item.id, tag_id)
        self.db.commit()

    # ── Internals ───────────────────────────────────────────────────────

    def _resolve_sources(self, topic: Topic) -> list[SourceConfig]:
        if topic.source_ids:
            selected = self.db.query(SourceConfig).filter(
                SourceConfig.id.in_(topic.source_ids),
                SourceConfig.is_active == True,
                SourceConfig.is_configured == True,
            ).all()
        else:
            selected = self.db.query(SourceConfig).filter(
                SourceConfig.is_active == True,
                SourceConfig.is_configured == True,
            ).all()
        if not topic.collection_model_ids or not topic.source_ids:
            return selected

        selected_ids = {source.id for source in selected}
        broad_sources = self.db.query(SourceConfig).filter(
            SourceConfig.is_active == True,
            SourceConfig.is_configured == True,
            SourceConfig.channel.in_(list(SEMANTIC_SEARCH_CHANNELS)),
        ).all()
        ai_research_sources = [
            source for source in broad_sources if _channel_value(source) == "ai_research"
        ]
        additions = ai_research_sources or [
            source for source in broad_sources if _channel_value(source) == "api_search"
        ]
        return [
            *selected,
            *(source for source in additions if source.id not in selected_ids),
        ]

    async def _translate_fetch_items(self, items: list[FetchItem], model: ModelConfig) -> list[FetchItem] | None:
        """Backward-compatible wrapper: attach translations without replacing originals."""
        from app.translation_service import translate_fetch_items_to_metadata
        await translate_fetch_items_to_metadata(items, model)
        return items

    def _persist_items(self, items: list[FetchItem], source_id: str, run_id: str,
                       topic_id: str | None = None, window_start: "datetime | None" = None,
                       window_end: "datetime | None" = None,
                       keywords: list[str] | None = None):
        persisted_count = 0
        for fi in items:
            parsed = parse_fetch_item(fi)
            if not parsed.is_meaningful:
                continue

            pub = _coerce_datetime(fi.published_at)

            # Strictly enforce the configured time window. Search connectors may
            # explicitly retain undated results for later source verification.
            if window_start is not None:
                if pub is None:
                    pub = _extract_date_from_text(f"{fi.title} {fi.content or ''} {fi.summary or ''}")
                if pub is None or (
                    pub is not None and _is_out_of_range(pub, window_start, window_end)
                ):
                    continue

            # Keyword relevance filtering: skip items that don't match the keyword combination
            # Keywords work together as a topic definition, not individually.
            allow_unfiltered = bool(
                isinstance(fi.raw_metadata, dict)
                and fi.raw_metadata.get("allow_unfiltered_results")
            )
            if isinstance(fi.raw_metadata, dict):
                review = fi.raw_metadata.get("quality_review")
                allow_unfiltered = allow_unfiltered or bool(
                    isinstance(review, dict)
                    and review.get("topic_relevance_score", 0) >= 60
                )
            # Enforcement candidates have already passed the dedicated
            # semantic review. Requiring two literal topic keywords here can
            # discard valid cases such as "检获受管制活龟" whose evidence is
            # expressed with different wording.
            if topic_id == "weekly-enforcement-intelligence":
                allow_unfiltered = True
            if keywords and not allow_unfiltered:
                metadata_text = ""
                if isinstance(fi.raw_metadata, dict):
                    metadata_text = " ".join(str(v) for v in fi.raw_metadata.values() if v)
                text = f"{fi.title} {fi.content or ''} {fi.summary or ''} {metadata_text}"
                matched_kws = [kw for kw in keywords if kw and kw.lower() in text.lower()]
                total_kw = len([kw for kw in keywords if kw])
                required_matches = 2 if total_kw >= 3 else 1
                if len(matched_kws) < required_matches:
                    continue
            item_id = fi.item_id(source_id)
            content_hash = _hash(_dedupe_fingerprint(fi.url, fi.title, parsed.content))
            try:
                existing = self.db.query(CollectedItem).filter(CollectedItem.id == item_id).first()
                if not existing:
                    existing = self.db.query(CollectedItem).filter(
                        CollectedItem.content_hash == content_hash,
                    ).first()
                if existing:
                    if parsed.content and parsed.content != existing.content:
                        existing.content = parsed.content
                    if parsed.summary and parsed.summary != existing.summary:
                        existing.summary = parsed.summary
                    if pub and not existing.published_at:
                        existing.published_at = pub
                    if topic_id and not existing.topic_id:
                        existing.topic_id = topic_id
                    existing.entities = _merge_json(existing.entities, parsed.entities)
                    existing.raw_metadata = _merge_json(existing.raw_metadata, parsed.metadata)
                    existing.updated_at = utc_now()
                else:
                    self.db.add(CollectedItem(
                        id=item_id, source_id=source_id, run_id=run_id,
                        topic_id=topic_id,
                        title=fi.title.strip(), content=parsed.content,
                        content_hash=content_hash,
                        summary=parsed.summary, url=fi.url,
                        language=fi.language, category=fi.category,
                        entities=parsed.entities,
                        quality_score=fi.quality_score,
                        relevance_score=fi.relevance_score,
                        published_at=pub,
                        collected_at=utc_now(),
                        raw_metadata=parsed.metadata,
                        status=ItemStatus.RAW,
                    ))
                    persisted_count += 1
                self.db.flush()
            except Exception:
                self.db.rollback()
        self.db.commit()
        return persisted_count

    def _select_enforcement_portfolio(
        self,
        items: list[FetchItem],
        window_start: datetime | None,
        target_total: int = 30,
    ) -> tuple[list[FetchItem], int]:
        """Fill a 30-day portfolio while preventing one jurisdiction dominating."""
        if not items:
            return [], 0

        from app.enforcement_review import (
            infer_candidate_china_relevance,
            infer_enforcement_jurisdiction,
        )

        query = self.db.query(CollectedItem).filter(
            CollectedItem.topic_id == "weekly-enforcement-intelligence",
        )
        if window_start is not None:
            query = query.filter(CollectedItem.published_at >= window_start)
        existing = query.all()
        slots = max(1, target_total)

        existing_counts: Counter[str] = Counter()
        existing_keys: set[str] = set()
        for stored in existing:
            stored_key = (stored.url or stored.title or "").strip().casefold()
            if stored_key:
                existing_keys.add(stored_key)
            metadata = stored.raw_metadata if isinstance(stored.raw_metadata, dict) else {}
            review = metadata.get("enforcement_review")
            jurisdiction = (
                str(review.get("jurisdiction") or "").strip()
                if isinstance(review, dict) else ""
            )
            if not jurisdiction:
                jurisdiction = infer_enforcement_jurisdiction(FetchItem(
                    title=stored.title,
                    content=stored.content,
                    summary=stored.summary,
                    url=stored.url,
                    raw_metadata=metadata,
                ))
            existing_counts[jurisdiction] += 1

        relevance_rank = {"strong": 0, "weak": 1, "major_non_china": 2}
        ranked = sorted(
            items,
            key=lambda item: (
                relevance_rank[infer_candidate_china_relevance(item)],
                existing_counts[infer_enforcement_jurisdiction(item)],
                infer_enforcement_jurisdiction(item) == "Hong Kong",
                -(item.relevance_score or 0),
            ),
        )
        selected: list[FetchItem] = []
        selected_counts: Counter[str] = Counter()
        seen_urls: set[str] = set()
        strong = [item for item in ranked if infer_candidate_china_relevance(item) == "strong"]
        weak = [item for item in ranked if infer_candidate_china_relevance(item) == "weak"]
        non_china = [item for item in ranked if infer_candidate_china_relevance(item) == "major_non_china"]
        non_china_groups: dict[str, list[FetchItem]] = {}
        for item in non_china:
            non_china_groups.setdefault(infer_enforcement_jurisdiction(item), []).append(item)
        diversified_non_china: list[FetchItem] = []
        while any(non_china_groups.values()):
            for jurisdiction in list(non_china_groups):
                if non_china_groups[jurisdiction]:
                    diversified_non_china.append(non_china_groups[jurisdiction].pop(0))
        non_china = diversified_non_china
        strong_target = max(1, int(slots * 0.5))
        china_target = max(strong_target, int(slots * 0.6))
        quota_ranked = [*strong[:strong_target], *weak[:max(0, china_target - min(len(strong), strong_target))]]
        quota_ranked.extend(item for item in [*strong, *weak, *non_china] if item not in quota_ranked)
        non_china_cap = max(1, int(slots * 0.4))
        non_china_selected = 0
        for item in quota_ranked:
            jurisdiction = infer_enforcement_jurisdiction(item)
            relevance = infer_candidate_china_relevance(item)
            if relevance == "major_non_china" and non_china_selected >= non_china_cap:
                continue
            if relevance == "strong":
                jurisdiction_cap = 10
            elif relevance == "weak":
                jurisdiction_cap = 10 if jurisdiction == "Hong Kong" else 8
            else:
                jurisdiction_cap = (
                    8 if jurisdiction == "Hong Kong"
                    else 3 if jurisdiction == "Unknown"
                    else 5
                )
            if selected_counts[jurisdiction] >= jurisdiction_cap:
                continue
            url_key = (item.url or item.title or "").strip().casefold()
            if (
                not url_key
                or url_key in existing_keys
                or url_key in seen_urls
            ):
                continue
            seen_urls.add(url_key)
            selected.append(item)
            if relevance == "major_non_china":
                non_china_selected += 1
            selected_counts[jurisdiction] += 1
            if len(selected) >= slots:
                break
        return selected, max(0, len(items) - len(selected))

    def _update_source(self, source: SourceConfig, items_found: int):
        source.last_sync_at = utc_now()
        source.items_collected += items_found


async def _hydrate_enforcement_candidates(
    items: list[FetchItem],
) -> list[FetchItem]:
    """Fetch shortlisted source pages concurrently; search snippets remain fallback evidence."""
    import httpx

    from app.web_content_extractor import extract_article_text

    semaphore = asyncio.Semaphore(6)
    timeout = httpx.Timeout(12.0, connect=8.0)
    limits = httpx.Limits(max_connections=8, max_keepalive_connections=4)

    async with httpx.AsyncClient(
        timeout=timeout,
        limits=limits,
        follow_redirects=True,
        headers={"User-Agent": "GatherInfo/0.8 (public-source verification)"},
    ) as client:
        async def hydrate(item: FetchItem) -> FetchItem:
            if not item.url or len((item.content or "").strip()) >= 1200:
                return item
            metadata = dict(item.raw_metadata or {})
            try:
                async with semaphore:
                    response = await client.get(item.url)
                response.raise_for_status()
                parsed = extract_article_text(response.text, str(response.url))
                article = str(parsed.get("content") or "").strip()
                if len(article) < 160:
                    metadata["source_hydration"] = "insufficient_content"
                    return replace(item, raw_metadata=metadata)
                metadata["source_hydration"] = "completed"
                metadata["resolved_url"] = str(response.url)
                source_published_at = parsed.get("published_at")
                if source_published_at:
                    metadata["date_verification"] = "source_page"
                return replace(
                    item,
                    content=article[:12000],
                    summary=item.summary or article[:500],
                    published_at=source_published_at or item.published_at,
                    raw_metadata=metadata,
                )
            except Exception as exc:
                metadata["source_hydration"] = "failed"
                metadata["source_hydration_error"] = type(exc).__name__
                return replace(item, raw_metadata=metadata)

        return list(await asyncio.gather(*(hydrate(item) for item in items)))


def _hash(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode()).hexdigest()


def _dedupe_fingerprint(url: str | None, title: str, content: str | None) -> str:
    """Return a stable cross-source identity without retaining tracking parameters."""
    if url:
        from urllib.parse import urlsplit, urlunsplit

        parsed = urlsplit(url.strip())
        normalized_url = urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path.rstrip("/"), "", ""))
        if normalized_url:
            return f"url:{normalized_url}"
    normalized_text = re.sub(r"\s+", " ", f"{title} {content or ''}").strip().lower()
    return f"text:{normalized_text}"


def _web_translation_model() -> ModelConfig:
    model = ModelConfig()
    model.provider = "web_fallback"
    model.model_name = "google-translate-web"
    model.base_url = ""
    model.api_key = ""
    model.temperature = 0.1
    model.max_tokens = 4096
    return model


def _extract_date_from_text(text: str) -> datetime | None:
    """Try to find a YYYY-MM-DD / YYYY/MM/DD / Chinese date inside the text."""
    if not text:
        return None
    patterns = [
        r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})",
        r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                parts = [int(x) for x in m.groups()]
                return datetime(parts[0], parts[1], parts[2], tzinfo=timezone.utc)
            except ValueError:
                continue
    return None

def _coerce_datetime(value):
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _is_out_of_range(
    published_at: datetime | None,
    window_start: datetime | None,
    window_end: datetime | None,
) -> bool:
    if published_at is None:
        return False
    pub = _as_aware_utc(published_at)
    start = _as_aware_utc(window_start)
    end = _as_aware_utc(window_end)
    if start is not None and pub < start:
        return True
    if end is not None and pub > end:
        return True
    return False


def _extract_date_from_text(text: str) -> datetime | None:
    """Extract common publication-date formats used by official sources."""
    if not text:
        return None

    for pattern in (
        r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})",
        r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日",
    ):
        match = re.search(pattern, text)
        if not match:
            continue
        try:
            year, month, day = (int(value) for value in match.groups())
            return datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            continue

    month_patterns = (
        (
            r"\b([A-Za-z]{3,9}\s+\d{1,2},?\s+\d{4})\b",
            ("%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y"),
        ),
        (
            r"\b(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})\b",
            ("%d %B %Y", "%d %b %Y"),
        ),
    )
    for pattern, formats in month_patterns:
        match = re.search(pattern, text)
        if not match:
            continue
        value = re.sub(r"\s+", " ", match.group(1)).strip()
        for date_format in formats:
            try:
                return datetime.strptime(value, date_format).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


def _filter_items_by_window(
    items: list[FetchItem],
    window_start: datetime | None,
    window_end: datetime | None,
) -> tuple[list[FetchItem], int]:
    if window_start is None:
        return list(items), 0
    accepted: list[FetchItem] = []
    rejected = 0
    for item in items:
        published_at = _coerce_datetime(item.published_at)
        if published_at is None:
            published_at = _extract_date_from_text(
                f"{item.title} {item.content or ''} {item.summary or ''}"
            )
        if published_at is None or _is_out_of_range(
            published_at, window_start, window_end
        ):
            rejected += 1
            continue
        accepted.append(replace(item, published_at=published_at.isoformat()))
    return accepted, rejected


def _topic_review_context(topic: Topic, semantic_prompt: str | None) -> dict:
    keywords = topic.keywords if isinstance(topic.keywords, list) else []
    return {
        "topic_id": topic.id,
        "name": topic.name,
        "description": topic.description or "",
        "semantic_instruction": semantic_prompt or topic.description_prompt or "",
        "keywords": [str(value) for value in keywords if value],
    }


def _channel_value(source: SourceConfig) -> str:
    return str(getattr(source.channel, "value", source.channel))


def _as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _merge_json(existing: dict | None, incoming: dict | None) -> dict:
    base = existing if isinstance(existing, dict) else {}
    extra = incoming if isinstance(incoming, dict) else {}
    return {**base, **extra}
