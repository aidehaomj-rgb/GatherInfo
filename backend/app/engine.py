"""
Collection Engine — the central orchestrator.

Flow:
    Topic → keywords → sources → connectors → FetchItems
    → dedup → persist (with topic_id) → auto-tag → return stats
"""
import asyncio
import logging
import math
import re
from collections import Counter
from dataclasses import replace
from datetime import date, datetime, timezone, timedelta
from uuid import uuid4
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.connectors.base import ConnectorRegistry, CollectResult, FetchItem
from app.collection_policy import evaluate_collection_policy
from app.collection_strategy import normalize_score
from app.content_parser import parse_fetch_item
from app.model_defaults import get_default_model
from app.tag_taxonomy import (
    CATEGORY_LABEL,
    classify_item_dimensions,
    dimension_values,
    normalize_category,
    tag_id_for,
)
from app.trade_semantics import is_semantically_relevant
from app.models import (
    CollectionBatch, CollectionRun, CollectedItem, ItemStatus,
    ItemTopicMembership, JobStatus, ModelConfig, SourceConfig, Tag, Topic,
)
from app.services.topic_item_query import item_in_topic

logger = logging.getLogger(__name__)
_translation_lock = asyncio.Lock()
# 进程内「停止采集」标记：手动停止后，同批次的后续信息源不再启动。
# 已入库的采集条目不受影响（保留），仅阻止尚未开始的信息源继续执行。
_stopped_batches: set[str] = set()

SEMANTIC_SEARCH_CHANNELS = frozenset({"ai_research", "api_search"})
MAX_PROGRESS_EVENTS = 120
MAX_ITEM_PROGRESS_EVENTS = 40
MAX_CANDIDATES_PER_SOURCE = 9
MAX_ENFORCEMENT_CANDIDATES_PER_SOURCE = 45
MAX_ENFORCEMENT_SEARCH_RESULTS_PER_SOURCE = 120
DEFAULT_CANDIDATES_PER_SOURCE = 9
MAX_CANDIDATES_PER_SOURCE = 160
SOURCE_COLLECTION_CONCURRENCY = 4
SOURCE_EXECUTION_TIMEOUT_SECONDS = 45
SEMANTIC_SOURCE_EXECUTION_TIMEOUT_SECONDS = 600
ENFORCEMENT_DISCOVERY_KEYWORDS = (
    "seiz", "intercept", "apprehend", "arrest", "charg", "detain",
    "confiscat", "contraband", "counterfeit", "undeclared", "unreported",
    "illegal import", "illegal export", "drug", "fentanyl", "cocaine",
    "methamphetamine", "weapon", "firearm", "tobacco", "wildlife",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def request_batch_stop(batch_id: str | None) -> None:
    """Mark a collection batch as stopped so its remaining sources are skipped."""
    if batch_id:
        _stopped_batches.add(batch_id)


def is_batch_stopped(batch_id: str | None) -> bool:
    return bool(batch_id and batch_id in _stopped_batches)


def _followup_gap_map(context, acceptance: dict) -> dict[str, list[str]]:
    """Translate measured acceptance gaps into planner search dimensions."""
    gaps = set(acceptance.get("gaps") or [])
    return {
        "countries": list(context.focus_countries) if "regions" in gaps else [],
        "languages": list(context.focus_languages) if "regions" in gaps else [],
        "policy_instruments": (
            list(context.policy_instruments)
            if gaps & {"items", "structure"} else []
        ),
        "products": (
            list(context.products)
            if gaps & {"items", "structure", "formal_completeness"} else []
        ),
        "source_grades": (
            list(context.policy.preferred_evidence_grades)
            if gaps & {
                "domains", "evidence_ratio", "source_concentration",
                "structure", "formal_completeness",
            }
            else []
        ),
    }


def _allocate_candidate_quotas(
    sources: list[SourceConfig], total_budget: int, per_source_limit: int = 160,
) -> dict[str, int]:
    """Allocate a bounded round budget with discovery-provider guarantees."""
    budget = max(1, min(300, int(total_budget)))
    quotas: dict[str, int] = {}
    remaining = budget
    source_cap = max(1, min(160, int(per_source_limit)))
    for source in sources:
        channel = _channel_value(source)
        desired = 20 if channel in SEMANTIC_SEARCH_CHANNELS else (
            12 if channel in {"rss", "official", "json_api"} else 4
        )
        quota = min(desired, source_cap, remaining)
        if quota <= 0:
            break
        quotas[str(source.id)] = quota
        remaining -= quota
    discovery_ids = [
        str(source.id) for source in sources
        if _channel_value(source) in SEMANTIC_SEARCH_CHANNELS
        and str(source.id) in quotas
    ]
    while remaining and discovery_ids:
        changed = False
        for source_id in discovery_ids:
            if remaining <= 0:
                break
            if quotas[source_id] < source_cap:
                quotas = {**quotas, source_id: quotas[source_id] + 1}
                remaining -= 1
                changed = True
        if not changed:
            break
    return quotas


def _batch_collection_plan_entries(sources: list[SourceConfig], context) -> list[dict]:
    """Return playbook-style source plan entries without candidate bodies."""
    from app.collection_strategy import build_source_profile

    entries: list[dict] = []
    for source in sources:
        profile = build_source_profile(source, context)
        entries.append({
            "source_id": str(source.id),
            "domain": profile.get("domain") or "",
            "display_name": profile.get("display_name") or str(source.id),
            "source_type": profile.get("source_type"),
            "preferred_method": profile.get("preferred_method"),
            "schedule": profile.get("schedule"),
            "crawl_delay_seconds": profile.get("crawl_delay_seconds"),
            "verification_status": profile.get("verification_status"),
            "robots_status": profile.get("robots_status"),
            "terms_status": profile.get("terms_status"),
            "llm_ingest_allowed": profile.get("llm_ingest_allowed"),
            "origin_resolution_required": profile.get("origin_resolution_required"),
            "automated_fetch_allowed": profile.get("automated_fetch_allowed"),
            "block_reason": profile.get("block_reason"),
            "entrypoints": profile.get("entrypoints") or [],
        })
    return entries


def _round_search_runs(
    sources: list[SourceConfig],
    results: list[CollectResult],
    queries: list[str],
) -> list[dict]:
    """Describe search/discovery work as counters, never candidate bodies."""
    result_by_source = {str(result.source_id): result for result in results}
    executed_at = utc_now().isoformat()
    rows: list[dict] = []
    for source in sources:
        result = result_by_source.get(str(source.id))
        is_search = _channel_value(source) in SEMANTIC_SEARCH_CHANNELS
        rows.append({
            "source_id": str(source.id),
            "domain": urlparse(
                str(source.base_url or source.homepage_url or source.api_endpoint or "")
            ).netloc.casefold(),
            "query_count": len(queries) if is_search else 0,
            "intent": "discovery" if is_search else "source_incremental",
            "executed_at": executed_at,
            "results_examined": int(getattr(result, "items_discovered", 0) or 0),
            "new_candidate_count": int(getattr(result, "items_new", 0) or 0)
            + int(getattr(result, "items_reused", 0) or 0),
            "truncated": bool(
                result and any("候选限额" in value for value in (result.error_log or []))
            ),
            "stop_reason": _result_stop_reason(result),
        })
    return rows


def _coverage_audit(
    context,
    sources: list[SourceConfig],
    results: list[CollectResult],
) -> list[dict]:
    """Summarise round coverage by declared source region."""
    result_by_source = {str(result.source_id): result for result in results}
    rows: list[dict] = []
    for source in sources:
        result = result_by_source.get(str(source.id))
        fetched = int(getattr(result, "items_new", 0) or 0) + int(
            getattr(result, "items_reused", 0) or 0
        )
        rejected = sum(int(getattr(result, field, 0) or 0) for field in (
            "items_date_rejected", "items_topic_rejected", "items_quality_rejected",
        ))
        blocked = int(getattr(result, "source_failures", 0) or 0)
        countries = source.country_focus if isinstance(source.country_focus, list) else []
        rows.append({
            "region": countries[0] if countries else "",
            "topic": getattr(context, "name", "") or getattr(context, "topic_id", ""),
            "languages": list(source.languages) if isinstance(source.languages, list) else [],
            "source_domains_checked": 1 if result else 0,
            "fetched_count": fetched,
            "rejected_count": rejected,
            "blocked_count": blocked,
            "gap_reason": _result_stop_reason(result) if not fetched else None,
        })
    return rows


def _result_stop_reason(result: CollectResult | None) -> str:
    if result is None:
        return "not_attempted"
    if result.status == JobStatus.FAILED:
        return "; ".join(result.error_log or ["source_failed"])[:500]
    if int(getattr(result, "items_discovered", 0) or 0) == 0:
        return "no_new_candidate"
    return "completed"


def _apply_forum_evidence_rules(
    items: list[FetchItem], topic_id: str | None, source: SourceConfig,
) -> tuple[list[FetchItem], int]:
    if topic_id != "foreign-trade-forum-risk-monitoring":
        return items, 0
    retained: list[FetchItem] = []
    rejected = 0
    source_group = str(source.source_group or "").casefold()
    for item in items:
        host = urlparse(item.url or "").netloc.casefold()
        is_community = (
            _channel_value(source) in {"social", "deepweb"}
            or any(marker in f"{source_group} {host}" for marker in (
                "forum", "community", "reddit", "facebook", "linkedin",
            ))
        )
        if not is_community:
            retained.append(item)
            continue
        metadata = dict(item.raw_metadata or {})
        profile = metadata.get("intelligence_profile")
        profile = profile if isinstance(profile, dict) else {}
        assessment = metadata.get("trade_assessment")
        assessment = dict(assessment) if isinstance(assessment, dict) else {}
        has_specifics = any(profile.get(field) for field in (
            "products", "actors", "routes", "countries",
        ))
        if not has_specifics or not str(assessment.get("facts") or "").strip():
            rejected += 1
            continue
        metadata["trade_assessment"] = {
            **assessment,
            "evidence_grade": "C",
            "evidence_notice": "单一来源风险线索，未经独立证实",
        }
        retained.append(replace(item, raw_metadata=metadata))
    return retained, rejected


def _topic_collection_keywords(topic: Topic) -> list[str]:
    raw_keywords = topic.keywords if isinstance(topic.keywords, list) else [topic.keywords]
    raw_synonyms = topic.synonyms if isinstance(getattr(topic, "synonyms", None), list) else []
    values = [*raw_keywords, *raw_synonyms]
    keywords = list(dict.fromkeys(
        str(value).strip() for value in values if str(value or "").strip()
    ))
    keywords = list(_dedupe_casefold(keywords))
    if topic.id != "weekly-enforcement-intelligence":
        return keywords

    seen = {keyword.casefold() for keyword in keywords}
    for keyword in ENFORCEMENT_DISCOVERY_KEYWORDS:
        if keyword.casefold() not in seen:
            keywords.append(keyword)
            seen.add(keyword.casefold())
    return keywords


def _dedupe_casefold(values: list[str]) -> tuple[str, ...]:
    result: tuple[str, ...] = ()
    for value in values:
        if not any(existing.casefold() == value.casefold() for existing in result):
            result = (*result, value)
    return result


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
        candidate_limit_override: int | None = None,
        topic_research_context=None,
        target_urls: list[str] | tuple[str, ...] | None = None,
        target_urls_mode: str = "discovery",
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

        policy = evaluate_collection_policy(source)
        self._record_progress(
            run,
            "compliance_review",
            policy.reason,
            status="completed" if policy.automated_fetch_allowed else "failed",
            detail={
                "automated_fetch_allowed": policy.automated_fetch_allowed,
                "llm_ingest_allowed": policy.llm_ingest_allowed,
                "content_depth": policy.content_depth,
            },
        )
        if not policy.automated_fetch_allowed:
            run.status = JobStatus.FAILED
            run.completed_at = utc_now()
            run.error_log = [policy.reason]
            self.db.commit()
            return CollectResult(
                run_id=run.id, source_id=source.id, status=JobStatus.FAILED,
                items=[], error_log=[policy.reason],
            )
        if not policy.llm_ingest_allowed:
            message = (
                f"{policy.reason} 当前正式采集连接器可能读取正文，因此在联网前阻止；"
                "该来源不得进入 LLM 或正式情报库。"
            )
            run.status = JobStatus.FAILED
            run.completed_at = utc_now()
            run.error_log = [message]
            self._record_progress(
                run, "compliance_blocked", message, status="failed",
                detail={"content_depth": policy.content_depth},
            )
            return CollectResult(
                run_id=run.id, source_id=source.id, status=JobStatus.FAILED,
                items=[], error_log=[message],
            )

        try:
            self._record_progress(
                run, "connecting", f"正在连接信息源“{source.name}”",
                detail={"source_id": source.id, "source_name": source.name},
            )
            connector = ConnectorRegistry.create(source)
            connector.set_collection_window(window_start, window_end)
            connector.set_target_urls(target_urls, mode=target_urls_mode)
        except ValueError as exc:
            run.status = JobStatus.FAILED
            run.error_log = [str(exc)]
            self._record_progress(
                run, "failed", f"信息源连接失败：{exc}", status="failed",
            )
            failed = CollectResult(run_id=run.id, source_id=source.id,
                                   status=JobStatus.FAILED, items=[], error_log=[str(exc)])
            self._mark_source_failure(source, run, failed)
            return failed

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
            runtime_max_items = candidate_limit_override or (
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
            failed = CollectResult(
                run_id=run.id, source_id=source.id, status=JobStatus.FAILED,
                items=[], error_log=[message],
            )
            self._mark_source_failure(source, run, failed)
            return failed
        if result.status == JobStatus.FAILED:
            self._mark_source_failure(source, run, result)
            self._record_progress(
                run, "failed", f"信息源采集失败：{'；'.join(result.error_log or ['未知错误'])}",
                status="failed",
            )
            return result

        run.status = JobStatus.RUNNING
        run.completed_at = None
        run.items_found = len(result.items)
        result.items_discovered = len(result.items)
        result.discovered_urls = tuple(dict.fromkeys(
            item.url.strip() for item in result.items if item.url and item.url.strip()
        ))
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

        if any(_coerce_datetime(item.published_at) is None for item in result.items):
            result.items = await _resolve_missing_candidate_dates(result.items)

        window_items, window_rejected = _filter_items_by_window(
            result.items, window_start, window_end,
            allow_text_date_extraction=topic_research_context is None,
        )
        early_duplicates: list[dict] = []
        if topic_id == "weekly-enforcement-intelligence":
            window_items, early_duplicates = (
                self._exclude_existing_enforcement_candidates(window_items)
            )
            if early_duplicates:
                self._record_progress(
                    run,
                    "deduplicated",
                    f"审核前已排除 {len(early_duplicates)} 条数据库已有案例，避免重复占用模型额度",
                    detail={"existing_skipped": len(early_duplicates)},
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
            candidate_limit = min(
                _candidate_review_limit(source),
                candidate_limit_override or MAX_CANDIDATES_PER_SOURCE,
            )
            retained_items = window_items[:candidate_limit]
        candidate_limited = max(0, len(window_items) - len(retained_items))
        result.items = retained_items
        result.items_date_rejected += window_rejected
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
        if result.items and not policy.llm_ingest_allowed:
            message = (
                f"{policy.reason} 候选仅作为线索返回，未发送至 LLM，"
                "也未进入正式情报库。"
            )
            result.items_failed += len(result.items)
            result.items = []
            result.status = JobStatus.FAILED
            result.error_log = [*(result.error_log or []), message]
            run.status = JobStatus.FAILED
            run.completed_at = utc_now()
            run.error_log = [*(run.error_log or []), message]
            self._record_progress(
                run, "compliance_blocked", message, status="failed",
                detail={"content_depth": policy.content_depth},
            )
            return result
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
                topic_research_context or _topic_review_context(
                    topic, semantic_prompt, window_start, window_end,
                ) if topic else None,
            )
            model_rejected = [
                rejection for rejection in rejected_items
                if "模型审核失败" in rejection.reason
            ]
            if model_rejected:
                result.model_failures += 1
                alternative = self.db.query(ModelConfig).filter(
                    ModelConfig.is_active == True,
                    ModelConfig.id != getattr(model, "id", None),
                ).first()
                if alternative:
                    retry_approved, retry_rejected = await curate_article_candidates(
                        [rejection.item for rejection in model_rejected],
                        alternative,
                        topic_research_context or _topic_review_context(
                            topic, semantic_prompt, window_start, window_end,
                        ) if topic else None,
                    )
                    approved_items = [*approved_items, *retry_approved]
                    rejected_items = [
                        *[rejection for rejection in rejected_items if rejection not in model_rejected],
                        *retry_rejected,
                    ]
                    if any("模型审核失败" in rejection.reason for rejection in retry_rejected):
                        result.model_failures += 1
        result.items = approved_items
        result.items, forum_rejected = _apply_forum_evidence_rules(
            result.items, topic_id, source,
        )
        result.items_quality_rejected += forum_rejected
        topic_rejected = sum(
            "排除词" in rejection.reason or "主题" in rejection.reason
            for rejection in rejected_items
        )
        result.items_topic_rejected += topic_rejected
        result.items_quality_rejected += len(rejected_items) - topic_rejected
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
        persisted_count, duplicates, reused_count = self._persist_items(
            result.items, source.id, run.id, topic_id, window_start, window_end,
            keywords, strict_date_metadata=topic_research_context is not None,
        )
        result.items_new = persisted_count
        result.items_reused += reused_count
        result.items_duplicate += len(duplicates) + len(early_duplicates)
        _sync_run_result_metrics(run, result, persisted_count)
        all_duplicates = [*early_duplicates, *duplicates]
        duplicate_count = len(all_duplicates)
        run.duplicate_items = all_duplicates or None
        run.items_updated = duplicate_count
        run.source_verdict = self._build_source_verdict(
            source, result, persisted_count, duplicate_count,
        )
        # 将本次采集结论回写到信息源配置，供「信息源管理」页面直接呈现
        source.last_verdict = run.source_verdict
        source.last_collected_at = utc_now()
        source.health_status = "healthy" if run.source_verdict.get("connectable") else "unreachable"
        source.health_checked_at = utc_now()
        source.last_error = None if run.source_verdict.get("connectable") else (
            run.source_verdict.get("summary") or "采集未完成连接"
        )
        self._record_progress(
            run, "persisted",
            f"已入库 {persisted_count} 条新信息，识别并跳过 {duplicate_count} 条重复或已存在信息",
            detail={"items_new": persisted_count, "duplicates_or_existing": duplicate_count},
        )
        for dup in all_duplicates[:MAX_ITEM_PROGRESS_EVENTS]:
            self._record_progress(
                run, "duplicate",
                f"重复信息：《{dup['title'] or '未命名信息'}》已存在，不重复入库",
                item_title=dup["title"] or None,
                detail={"existing_item_id": dup["existing_item_id"], "matched_by": dup["matched_by"]},
                commit=False,
            )
        self.db.commit()
        self._update_source(source, persisted_count)
        self._mark_source_success(source, result)
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
    ) -> tuple[list[FetchItem], list[dict]]:
        """Remove known cases before costly model review.

        Returns (retained, duplicates) — 被排除的重复项保留标题/链接，
        供任务查看按“重复/新增”分类展示。
        """
        from app.services.topic_item_query import filter_items_by_topic

        existing = filter_items_by_topic(self.db.query(
            CollectedItem.id,
            CollectedItem.url,
            CollectedItem.title,
            CollectedItem.content,
        ), "weekly-enforcement-intelligence").all()
        existing_keys: dict[str, str] = {
            _dedupe_fingerprint(row.url, row.title or "", row.content): row.id
            for row in existing
        }
        retained: list[FetchItem] = []
        duplicates: list[dict] = []
        seen: set[str] = set()
        for item in items:
            key = _dedupe_fingerprint(item.url, item.title, item.content)
            if key in existing_keys or key in seen:
                duplicates.append({
                    "title": (item.title or "").strip(),
                    "url": item.url or "",
                    "existing_item_id": existing_keys.get(key),
                    "matched_by": "enforcement_dedupe",
                })
                continue
            seen.add(key)
            retained.append(item)
        return retained, duplicates

    def _enforcement_jurisdiction_counts(
        self, window_start: datetime | None,
    ) -> Counter[str]:
        from app.enforcement_review import infer_enforcement_jurisdiction

        from app.services.topic_item_query import filter_items_by_topic

        query = filter_items_by_topic(
            self.db.query(CollectedItem), "weekly-enforcement-intelligence",
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
        collection_window_start: datetime | None = None,
        collection_window_end: datetime | None = None,
    ) -> list[CollectResult]:
        """Run the six optimized topics through a bounded two-round loop."""
        from app.collection_loop import (
            dynamic_policy, evaluate_topic_batch, structured_gaps,
        )
        from app.collection_strategy import (
            build_source_plan, build_source_profile, candidate_budget,
        )
        from app.research_planner import build_followup_queries
        from app.topic_research_context import (
            SIX_OPTIMIZED_TOPIC_IDS, build_topic_research_context,
        )

        topic = self.db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            raise ValueError(f"Topic not found: {topic_id}")
        if topic_id not in SIX_OPTIMIZED_TOPIC_IDS:
            return await self._collect_topic_round(
                topic_id, research_prompt, research_model_id, only_source_ids,
                collection_window_start, collection_window_end,
            )

        window_start, window_end = _topic_collection_window(
            topic,
            requested_start=collection_window_start,
            requested_end=collection_window_end,
        )
        prompt = _topic_collection_prompt(self.db, topic, research_prompt)
        context = build_topic_research_context(
            topic,
            prompt=prompt,
            window_start=window_start.date(),
            window_end=window_end.date(),
        )
        policy = dynamic_policy(self.db, context)
        max_rounds = min(2, max(1, context.policy.max_rounds))
        batch_id = f"batch-{uuid4().hex[:12]}"
        source_candidates = self._resolve_source_candidates(topic)
        sources = [
            source for source in source_candidates
            if evaluate_collection_policy(source).content_depth == "full"
            and ConnectorRegistry.get(_channel_value(source)) is not None
        ]
        if only_source_ids:
            allowed = set(only_source_ids)
            source_candidates = [
                source for source in source_candidates if source.id in allowed
            ]
            sources = [source for source in sources if source.id in allowed]
        if not sources:
            raise ValueError(
                "该主题没有通过来源核验、robots/条款与 LLM 使用许可的正式信息源；"
                "请先查看 /sources/collection-readiness。"
            )
        collection_plan = _batch_collection_plan_entries(source_candidates, context)
        for source in sources:
            source.collection_profile = build_source_profile(source, context)
        self.db.commit()
        rotation_per_week = min(300, max(24, math.ceil(len(sources) / 4)))
        plan = build_source_plan(sources, rotation_limit=rotation_per_week * 2)
        first_rotation = plan.rotation[:rotation_per_week]
        second_rotation = (
            plan.rotation[rotation_per_week:rotation_per_week * 2]
            or first_rotation
        )
        round_one_ids = tuple(str(source.id) for source in (*plan.core, *plan.discovery, *first_rotation))
        round_two_ids = tuple(str(source.id) for source in (*plan.core, *plan.discovery, *second_rotation))
        batch = CollectionBatch(
            id=batch_id,
            topic_id=topic_id,
            status="running",
            current_round=0,
            max_rounds=max_rounds,
            target=policy,
            gaps=[],
            source_plan={
                "core": [str(source.id) for source in plan.core],
                "discovery": [str(source.id) for source in plan.discovery],
                "round_1_rotation": [str(source.id) for source in first_rotation],
                "round_2_rotation": [str(source.id) for source in second_rotation],
                "source_pool_size": len(source_candidates),
                "eligible_source_count": len(sources),
                "blocked_source_count": max(0, len(source_candidates) - len(sources)),
                "collection_plan": collection_plan,
            },
            round_summaries=[],
            started_at=utc_now(),
        )
        self.db.add(batch)
        self.db.commit()

        combined: list[CollectResult] = []
        seen_discovered_urls: set[str] = set()
        acceptance: dict = evaluate_topic_batch(self.db, context, policy)
        try:
            for round_number in range(1, max_rounds + 1):
                batch.current_round = round_number
                self.db.commit()
                ids = round_one_ids if round_number == 1 else round_two_ids
                gap_map = _followup_gap_map(context, acceptance)
                queries = (
                    None if round_number == 1
                    else build_followup_queries(context, gap_map, max_queries=20)
                )
                round_budget = candidate_budget(
                    int(policy["target_items"]) - int(acceptance["metrics"]["items"]),
                    context.policy.candidate_floor,
                    context.policy.candidate_ceiling,
                )
                results = await self._collect_topic_round(
                    topic_id,
                    research_prompt,
                    research_model_id,
                    list(ids),
                    window_start,
                    window_end,
                    batch_id=batch_id,
                    research_context=context,
                    round_number=round_number,
                    gaps=gap_map,
                    planned_queries=queries,
                    candidate_budget_limit=round_budget,
                    per_source_review_limit=context.policy.per_source_review_limit,
                )
                combined.extend(results)
                acceptance = evaluate_topic_batch(self.db, context, policy)
                discovered_urls = {
                    url
                    for result in results
                    for url in (
                        result.discovered_urls
                        or tuple(item.url for item in result.items if item.url)
                    )
                    if url
                }
                new_discovered_urls = discovered_urls - seen_discovered_urls
                seen_discovered_urls = seen_discovered_urls | discovered_urls
                round_summary = {
                    "round": round_number,
                    "candidate_budget": round_budget,
                    "sources_attempted": len(results),
                    "items_new": sum(result.items_new for result in results),
                    "items_reused": sum(getattr(result, "items_reused", 0) for result in results),
                    "new_urls_seen": len(new_discovered_urls),
                    "search_runs": _round_search_runs(
                        [source for source in sources if str(source.id) in ids],
                        results,
                        queries or [],
                    ),
                    "coverage_audit": _coverage_audit(
                        context,
                        [source for source in sources if str(source.id) in ids],
                        results,
                    ),
                    "acceptance": acceptance,
                }
                batch.round_summaries = [*(batch.round_summaries or []), round_summary]
                funnel_fields = (
                    "items_discovered", "items_date_rejected", "items_topic_rejected",
                    "items_quality_rejected", "items_new", "items_reused",
                    "items_duplicate", "model_failures", "source_failures",
                )
                funnel = {
                    field: sum(int(getattr(result, field, 0) or 0) for result in combined)
                    for field in funnel_fields
                }
                batch.metrics = {**dict(acceptance.get("metrics") or {}), **funnel}
                batch.acceptance = acceptance
                batch.gaps = structured_gaps(acceptance)
                self.db.commit()
                if acceptance.get("passed"):
                    batch.stop_reason = "dynamic_target_met"
                    break
                if not new_discovered_urls:
                    batch.stop_reason = "no_new_urls"
                    break
            batch.status = "completed"
            batch.stop_reason = batch.stop_reason or "max_rounds_reached"
        except Exception as exc:
            batch.status = "failed"
            batch.stop_reason = f"collection_error:{type(exc).__name__}"
            raise
        finally:
            batch.completed_at = utc_now()
            self.db.commit()
            _stopped_batches.discard(batch_id)
        return combined

    async def _collect_topic_round(
        self,
        topic_id: str,
        research_prompt: str | None = None,
        research_model_id: str | None = None,
        only_source_ids: list[str] | None = None,
        collection_window_start: datetime | None = None,
        collection_window_end: datetime | None = None,
        *,
        batch_id: str | None = None,
        research_context=None,
        round_number: int = 1,
        gaps: dict[str, list[str]] | None = None,
        planned_queries: list[str] | None = None,
        candidate_budget_limit: int = 120,
        per_source_review_limit: int = 160,
    ) -> list[CollectResult]:
        """Execute one network round and persist only approved formal items."""
        topic = self.db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            raise ValueError(f"Topic not found: {topic_id}")
        if topic.id == "weekly-enforcement-intelligence":
            self._backfill_enforcement_metadata()

        sources = self._resolve_sources(topic)
        if only_source_ids:
            allowed = set(only_source_ids)
            sources = [source for source in sources if source.id in allowed]
        if not sources:
            raise ValueError(
                "该主题没有通过来源核验、robots/条款与 LLM 使用许可的正式信息源；"
                "请先查看 /sources/collection-readiness。"
            )
        source_ids = [s.id for s in sources]
        source_quotas = _allocate_candidate_quotas(
            sources, candidate_budget_limit, per_source_review_limit,
        )
        sources = [source for source in sources if str(source.id) in source_quotas]
        source_ids = [s.id for s in sources]
        keywords = _topic_collection_keywords(topic)

        window_days = getattr(topic, "collect_window_days", None) or 0
        window_start, window_end = _topic_collection_window(
            topic,
            requested_start=collection_window_start,
            requested_end=collection_window_end,
        )

        # All source runs in a bounded loop share one batch id.
        batch_id = batch_id or f"batch-{uuid4().hex[:12]}"

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

        semantic_queries: list[str] = list(planned_queries or [])
        effective_research_prompt = _topic_collection_prompt(self.db, topic, research_prompt)
        planning_window_days = _planning_window_days(
            window_start, window_end, fallback_days=window_days or 7,
        )
        planning_start_date, planning_end_date = _planning_window_dates(
            window_start, window_end,
        )
        if not semantic_queries and any(_channel_value(source) in SEMANTIC_SEARCH_CHANNELS for source in sources):
            try:
                from app.research_planner import build_research_queries
                semantic_queries = await build_research_queries(
                    topic,
                    effective_research_prompt or "",
                    research_model,
                    max_queries=40 if topic.id == "weekly-enforcement-intelligence" else 12,
                    window_days=planning_window_days,
                    window_start_date=planning_start_date,
                    window_end_date=planning_end_date,
                    research_context=research_context,
                    round_number=round_number,
                    gaps=gaps,
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
            if is_batch_stopped(batch_id):
                return CollectResult(
                    run_id="", source_id=source.id, status=JobStatus.FAILED,
                    items=[], error_log=["Collection stopped manually from UI"],
                )
            async with semaphore:
                if is_batch_stopped(batch_id):
                    return CollectResult(
                        run_id="", source_id=source.id, status=JobStatus.FAILED,
                        items=[], error_log=["Collection stopped manually from UI"],
                    )
                return await self.collect_from_source(
                    source.id,
                    semantic_queries if _channel_value(source) in SEMANTIC_SEARCH_CHANNELS and semantic_queries else keywords,
                    topic.id,
                    window_start,
                    window_end,
                    batch_id,
                    collection_models[index % len(collection_models)] if collection_models else default_model,
                    effective_research_prompt,
                    source_quotas.get(str(source.id)),
                    research_context,
                    target_urls=topic.target_urls,
                    target_urls_mode=research_context.target_urls_mode,
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
        from app.services.topic_item_query import filter_items_by_topic
        items = filter_items_by_topic(self.db.query(CollectedItem), topic_id).all()
        applied = 0
        for item in items:
            text = f"{item.title} {item.content or ''}".lower()
            for rule in rules:
                if rule.get("keyword", "").lower() in text:
                    tag_id = rule.get("tag", "")
                    if not tag_id:
                        continue
                    if ":" in tag_id:
                        ns, val = tag_id.split(":", 1)
                    else:
                        # 无命名空间的自由标签统一归一化到受控分类，避免标签爆炸
                        val = normalize_category(tag_id)
                        if not val:
                            continue
                        ns = "category"
                        tag_id = f"category:{val}"
                    self.ensure_tag(tag_id, ns, val, CATEGORY_LABEL.get(val) if ns == "category" else None)
                    if self.tag_item(item.id, tag_id):
                        applied += 1
        self.db.commit()
        return applied

    def _apply_suggested_tags(self, topic_id: str):
        from app.services.topic_item_query import filter_items_by_topic
        items = filter_items_by_topic(self.db.query(CollectedItem), topic_id).all()
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
                # 无命名空间或非受控分类的自由标签，统一归一化到受控分类
                if ns == "general":
                    norm = normalize_category(val)
                    if not norm:
                        continue
                    ns, val, tag_id = "category", norm, f"category:{norm}"
                self.ensure_tag(tag_id, ns, val, CATEGORY_LABEL.get(val) if ns == "category" else None)
                self.tag_item(item.id, tag_id)

            # Always apply a category tag if item has a category（归一化到受控分类）
            if item.category:
                normalized = normalize_category(item.category)
                if normalized:
                    if normalized != item.category:
                        item.category = normalized
                    tag_id = f"category:{normalized}"
                    self.ensure_tag(tag_id, "category", normalized, CATEGORY_LABEL.get(normalized))
                    self.tag_item(item.id, tag_id)

            # 多维受控标签：按语义给条目打 policy/impact/region/evidence 维度标签
            self._apply_dimension_tags(item)
        self.db.commit()

    def _apply_dimension_tags(self, item) -> None:
        """按受控多维标签体系给单条条目打维度标签（policy/impact/category/region/evidence）。"""
        metadata = item.raw_metadata if isinstance(item.raw_metadata, dict) else {}
        review = metadata.get("enforcement_review") if isinstance(metadata, dict) else {}
        china_relevance = ""
        if isinstance(review, dict):
            china_relevance = str(review.get("china_relevance") or "").strip()

        dims = classify_item_dimensions(
            title=item.title or "",
            content=item.content or "",
            category=item.category,
            china_relevance=china_relevance,
        )
        for dim, values in dims.items():
            for value in values:
                label = dimension_values(dim).get(value)
                tag_id = tag_id_for(dim, value)
                self.ensure_tag(tag_id, dim, value, label)
                self.tag_item(item.id, tag_id)

    # ── Internals ───────────────────────────────────────────────────────

    def _resolve_source_candidates(self, topic: Topic) -> list[SourceConfig]:
        """Resolve configured topic sources plus semantic discovery sources."""
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

    def _resolve_sources(self, topic: Topic) -> list[SourceConfig]:
        return [
            source for source in self._resolve_source_candidates(topic)
            if evaluate_collection_policy(source).content_depth == "full"
            and ConnectorRegistry.get(_channel_value(source)) is not None
        ]

    async def _translate_fetch_items(self, items: list[FetchItem], model: ModelConfig) -> list[FetchItem] | None:
        """Backward-compatible wrapper: attach translations without replacing originals."""
        from app.translation_service import translate_fetch_items_to_metadata
        await translate_fetch_items_to_metadata(items, model)
        return items

    def _persist_items(self, items: list[FetchItem], source_id: str, run_id: str,
                       topic_id: str | None = None, window_start: "datetime | None" = None,
                       window_end: "datetime | None" = None,
                       keywords: list[str] | None = None,
                       strict_date_metadata: bool = False):
        persisted_count = 0
        reused_count = 0
        duplicates: list[dict] = []
        self._source_cache = getattr(self, "_source_cache", {})
        _source_obj = self._source_cache.get(source_id)
        if _source_obj is None:
            _source_obj = self.db.query(SourceConfig).filter(
                SourceConfig.id == source_id
            ).first()
            self._source_cache[source_id] = _source_obj
        _source_channel = getattr(_source_obj, "channel", None) if _source_obj else None
        _curated_channel = _source_channel in ("rss", "official", "json_api")
        for fi in items:
            fi = replace(fi, url=_canonical_source_url(fi.url))
            parsed = parse_fetch_item(fi)
            if not parsed.is_meaningful or not (fi.url or "").strip():
                continue

            pub = _coerce_datetime(fi.published_at)

            # Strictly enforce the configured time window. Search connectors may
            # explicitly retain undated results for later source verification.
            if window_start is not None:
                if pub is None and not strict_date_metadata:
                    pub = _extract_date_from_text(f"{fi.title} {fi.content or ''} {fi.summary or ''}")
                if pub is None or (
                    pub is not None and _is_out_of_range(pub, window_start, window_end)
                ):
                    continue

            # Keyword relevance filtering: skip items that don't match the keyword combination
            # Keywords work together as a topic definition, not individually.
            required_matches = 1 if _curated_channel else None
            # Connector output is untrusted external data.  Only the shared
            # topic-quality gate may authorize semantic admission; a connector
            # cannot bypass topic rules by setting its own metadata flag.
            allow_unfiltered = False
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
                if required_matches is None:
                    required_matches = 2 if total_kw >= 3 else 1
                if len(matched_kws) < required_matches:
                    # 语义兜底：字面关键词未命中时，用受控政策工具词表判定语义相关性，
                    # 避免中英措辞差异导致的漏采（如英文讲 third-country transshipment）。
                    # 仅对绑定了语义画像的贸易类主题生效，关键矿产/军工主题不受影响。
                    if not is_semantically_relevant(text, topic_id):
                        continue
            item_id = fi.item_id(source_id)
            content_hash = _hash(_dedupe_fingerprint(fi.url, fi.title, parsed.content))
            provenance = _source_provenance(fi, pub, content_hash)
            parsed_metadata = _merge_json(
                parsed.metadata, {"source_provenance": provenance},
            )
            try:
                existing = self.db.query(CollectedItem).filter(CollectedItem.id == item_id).first()
                matched_by = "url" if existing else None
                if not existing:
                    existing = self.db.query(CollectedItem).filter(
                        CollectedItem.content_hash == content_hash,
                    ).first()
                    if existing:
                        matched_by = "content_hash"
                was_existing = existing is not None
                if existing:
                    # 与本地库比对命中已有条目 → 记录为“重复”，保留标题供任务查看展示
                    duplicates.append({
                        "title": (fi.title or "").strip(),
                        "url": fi.url or "",
                        "existing_item_id": existing.id,
                        "matched_by": matched_by or "unknown",
                    })
                    if fi.title.strip() and fi.title.strip() != existing.title:
                        existing.title = fi.title.strip()
                    if parsed.content and parsed.content != existing.content:
                        existing.content = parsed.content
                    if parsed.summary and parsed.summary != existing.summary:
                        existing.summary = parsed.summary
                    if fi.language and fi.language != existing.language:
                        existing.language = fi.language
                    if fi.category and fi.category != existing.category:
                        existing.category = fi.category
                    existing.quality_score = max(
                        normalize_score(existing.quality_score),
                        normalize_score(fi.quality_score),
                    )
                    existing.relevance_score = max(
                        normalize_score(existing.relevance_score),
                        normalize_score(fi.relevance_score),
                    )
                    if pub and not existing.published_at:
                        existing.published_at = pub
                    elif not strict_date_metadata and not existing.published_at and fi.url:
                        _url_date = _extract_date_from_text(fi.url)
                        if _url_date:
                            existing.published_at = _url_date
                    if topic_id and not existing.topic_id:
                        existing.topic_id = topic_id
                    existing.entities = _merge_json(existing.entities, parsed.entities)
                    existing.raw_metadata = _merge_json(existing.raw_metadata, parsed_metadata)
                    existing.updated_at = utc_now()
                else:
                    if pub is None and not strict_date_metadata and fi.url:
                        pub = _extract_date_from_text(fi.url)
                    existing = CollectedItem(
                        id=item_id, source_id=source_id, run_id=run_id,
                        topic_id=topic_id,
                        title=fi.title.strip(), content=parsed.content,
                        content_hash=content_hash,
                        summary=parsed.summary, url=fi.url,
                        language=fi.language, category=fi.category,
                        entities=parsed.entities,
                        quality_score=normalize_score(fi.quality_score),
                        relevance_score=normalize_score(fi.relevance_score),
                        published_at=pub,
                        collected_at=utc_now(),
                        raw_metadata=parsed_metadata,
                        status=ItemStatus.RAW,
                    )
                    self.db.add(existing)
                    persisted_count += 1
                self.db.flush()
                if topic_id:
                    metadata = fi.raw_metadata if isinstance(fi.raw_metadata, dict) else {}
                    assessment = (
                        metadata.get("trade_assessment")
                        or metadata.get("quality_review")
                        or metadata.get("enforcement_review")
                    )
                    membership_created = self._ensure_topic_membership(
                        existing.id, topic_id, run_id, fi.relevance_score,
                        assessment if isinstance(assessment, dict) else None,
                    )
                    reused_count += int(was_existing and membership_created)
            except Exception:
                self.db.rollback()
        self.db.commit()
        return persisted_count, duplicates, reused_count

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
            item_in_topic("weekly-enforcement-intelligence"),
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

    def _build_source_verdict(
        self,
        source: SourceConfig,
        result: CollectResult,
        persisted_count: int,
        duplicate_count: int,
    ) -> dict:
        """为一次已完成的信息源采集生成明确结论。

        结论维度：可连接 / 可爬取 / 可下载 / 语言类型。
        - 可连接：连接器创建成功且完成抓取（能走到本方法即已连接）。
        - 可爬取：源返回了可读取的候选项（页面/API 内容可解析）。
        - 可下载：成功获取到正文或摘要（内容真正落地）。

        数量口径（自洽）：
        - ``items_found`` = 符合采集标准的信息数 = 新增 + 重复（真正进入本地库比对）。
        - ``items_candidates`` = 审核后保留的候选数（进入 LLM 审核前的数量，供参考）。
        """
        items = result.items or []
        matched = persisted_count + duplicate_count
        with_content = sum(1 for item in items if (item.content or "").strip())
        with_summary = sum(1 for item in items if (item.summary or "").strip())

        languages: list[str] = list(dict.fromkeys(
            item.language for item in items if item.language
        ))
        if not languages:
            languages = self._infer_languages(items)
        if not languages and getattr(source, "languages", None):
            languages = list(source.languages)

        # 能走到本方法说明连接器创建成功且抓取流程已完成
        connectable = True
        crawlable = matched > 0 or len(items) > 0
        downloadable = with_content > 0 or with_summary > 0

        parts: list[str] = []
        parts.append("可连接" if connectable else "不可连接")
        parts.append("可爬取" if crawlable else "未爬取到内容")
        parts.append("可下载" if downloadable else "未获取到正文")
        if languages:
            lang_label = "、".join(_language_label(lang) for lang in languages)
            parts.append(f"语言：{lang_label}")

        return {
            "connectable": bool(connectable),
            "crawlable": bool(crawlable),
            "downloadable": bool(downloadable),
            "languages": languages,
            "channel": _channel_value(source),
            "items_found": matched,
            "items_candidates": len(items),
            "items_new": persisted_count,
            "items_duplicate": duplicate_count,
            "summary": "；".join(parts),
        }

    @staticmethod
    def _infer_languages(items: list[FetchItem]) -> list[str]:
        langs: list[str] = []
        for item in items:
            text = f"{item.title or ''} {item.content or ''} {item.summary or ''}"
            if re.search(r"[\u4e00-\u9fff]", text):
                if "zh" not in langs:
                    langs.append("zh")
            if re.search(r"[a-zA-Z]{3,}", text):
                if "en" not in langs:
                    langs.append("en")
        return langs

    def _update_source(self, source: SourceConfig, items_found: int):
        source.last_sync_at = utc_now()
        source.items_collected += items_found

    def _mark_source_failure(
        self, source: SourceConfig, run: CollectionRun, result: CollectResult,
    ) -> None:
        """Apply an ephemeral cooldown without changing operator activation."""
        failures = int(source.consecutive_failures or 0) + 1
        source.consecutive_failures = failures
        result.source_failures = int(result.source_failures or 0) + 1
        run.source_failures = result.source_failures
        if failures >= 3:
            hours = min(72, 6 * (2 ** min(3, failures - 3)))
            source.cooldown_until = utc_now() + timedelta(hours=hours)
        profile = dict(source.collection_profile or {})
        source.collection_profile = {
            **profile,
            "last_failure_at": utc_now().isoformat(),
            "consecutive_failures": failures,
            "runtime_state": "paused_drift_review" if failures >= 3 else "degraded",
            "stop_reason": (
                "连续3次失败，进入页面漂移人工复核"
                if failures >= 3 else "来源执行失败"
            ),
        }
        self.db.commit()

    def _mark_source_success(
        self, source: SourceConfig, result: CollectResult,
    ) -> None:
        profile = dict(source.collection_profile or {})
        discovered = int(result.items_discovered or len(result.items))
        source.consecutive_failures = 0
        source.cooldown_until = None
        source.collection_profile = {
            **profile,
            "last_success_at": utc_now().isoformat(),
            "last_discovered": discovered,
            "last_items_new": int(result.items_new or 0),
            "last_items_reused": int(result.items_reused or 0),
            "runtime_state": "ready",
            "stop_reason": None,
            "date_completeness": round(
                max(0, discovered - int(result.items_date_rejected or 0)) / discovered, 4
            ) if discovered else 0.0,
        }

    def _ensure_topic_membership(
        self,
        item_id: str,
        topic_id: str,
        run_id: str | None,
        relevance_score: float | None,
        assessment: dict | None = None,
    ) -> bool:
        bounded_relevance = _bounded_relevance(relevance_score)
        membership = self.db.query(ItemTopicMembership).filter(
            ItemTopicMembership.item_id == item_id,
            ItemTopicMembership.topic_id == topic_id,
        ).first()
        if membership:
            details = dict(assessment or {})
            membership.last_run_id = run_id or membership.last_run_id
            if bounded_relevance is not None:
                membership.relevance_score = bounded_relevance
            membership.last_seen_at = utc_now()
            membership.relevance_tier = details.get("relevance_tier") or membership.relevance_tier
            membership.evidence_grade = details.get("evidence_grade") or membership.evidence_grade
            membership.customs_value = details.get("customs_value") or membership.customs_value
            membership.information_type = details.get("information_type") or membership.information_type
            membership.relevance_metadata = {
                **dict(membership.relevance_metadata or {}), **details,
            } or None
            return False
        details = dict(assessment or {})
        self.db.add(ItemTopicMembership(
            item_id=item_id,
            topic_id=topic_id,
            first_run_id=run_id,
            last_run_id=run_id,
            relevance_score=bounded_relevance,
            relevance_tier=details.get("relevance_tier"),
            evidence_grade=details.get("evidence_grade"),
            customs_value=details.get("customs_value"),
            information_type=details.get("information_type"),
            relevance_metadata=details or None,
            first_seen_at=utc_now(),
            last_seen_at=utc_now(),
        ))
        return True


async def _hydrate_enforcement_candidates(
    items: list[FetchItem],
) -> list[FetchItem]:
    """Fetch shortlisted source pages concurrently; search snippets remain fallback evidence."""
    from app.safe_fetch import public_async_client
    from app.web_content_extractor import extract_article_text

    semaphore = asyncio.Semaphore(6)
    async with public_async_client(
        timeout=12,
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


async def _resolve_missing_candidate_dates(
    items: list[FetchItem],
) -> list[FetchItem]:
    """Safely read source metadata before rejecting an otherwise valid lead."""
    from app.connectors.tavily_search import _resolve_page_metadata
    from app.safe_fetch import public_async_client

    semaphore = asyncio.Semaphore(6)
    async with public_async_client(timeout=15) as client:
        async def resolve(item: FetchItem) -> FetchItem:
            if _coerce_datetime(item.published_at) is not None or not item.url:
                return item
            async with semaphore:
                metadata = await _resolve_page_metadata(client, item.url)
            published = metadata.get("published_at") if metadata else None
            if not published:
                return item
            raw = dict(item.raw_metadata or {})
            raw = {
                **raw,
                "date_verification": "source_page_metadata",
                "updated_at": metadata.get("updated_at") or raw.get("updated_at"),
            }
            content = item.content
            resolved_content = str(metadata.get("content") or "").strip()
            if len((content or "").strip()) < 180 and len(resolved_content) >= 180:
                content = resolved_content[:12000]
            return replace(
                item, published_at=published, content=content, raw_metadata=raw,
            )

        return list(await asyncio.gather(*(resolve(item) for item in items)))


def _hash(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode()).hexdigest()


def _bounded_relevance(value: float | None) -> float | None:
    try:
        return normalize_score(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _sync_run_result_metrics(
    run: CollectionRun,
    result: CollectResult,
    persisted_count: int,
) -> None:
    """Persist the final funnel counters after window and LLM review."""
    run.items_new = persisted_count
    run.items_failed = int(result.items_failed or 0)
    run.items_discovered = int(result.items_discovered or 0)
    run.items_date_rejected = int(result.items_date_rejected or 0)
    run.items_topic_rejected = int(result.items_topic_rejected or 0)
    run.items_quality_rejected = int(result.items_quality_rejected or 0)
    run.items_reused = int(result.items_reused or 0)
    run.items_duplicate = int(result.items_duplicate or 0)
    run.model_failures = int(result.model_failures or 0)
    run.source_failures = int(result.source_failures or 0)
    run.error_log = list(result.error_log) if result.error_log else None


def _candidate_review_limit(source: SourceConfig) -> int:
    """Honor per-source budgets while keeping one bad config bounded."""
    try:
        configured = int(source.max_items_per_run or DEFAULT_CANDIDATES_PER_SOURCE)
    except (TypeError, ValueError):
        configured = DEFAULT_CANDIDATES_PER_SOURCE
    return max(1, min(configured, MAX_CANDIDATES_PER_SOURCE))


def _dedupe_fingerprint(url: str | None, title: str, content: str | None) -> str:
    """Return a stable cross-source identity without retaining tracking parameters."""
    if url:
        normalized_url = _canonical_source_url(url)
        if normalized_url:
            return f"url:{normalized_url}"
    normalized_text = re.sub(r"\s+", " ", f"{title} {content or ''}").strip().lower()
    return f"text:{normalized_text}"


def _canonical_source_url(url: str | None) -> str | None:
    """Strip tracking parameters while preserving evidence-bearing query keys."""
    if not url:
        return None
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    parsed = urlsplit(url.strip())
    tracking = {"fbclid", "gclid", "spm", "ref", "source"}
    query = urlencode([
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_")
        and key.casefold() not in tracking
    ])
    return urlunsplit((
        parsed.scheme.casefold(), parsed.netloc.casefold(),
        parsed.path.rstrip("/") or "/", query, "",
    ))


def _source_provenance(
    item: FetchItem, published_at: datetime | None, content_hash: str,
) -> dict:
    metadata = item.raw_metadata if isinstance(item.raw_metadata, dict) else {}
    locator = metadata.get("locator")
    locator = dict(locator) if isinstance(locator, dict) else {}
    return {
        "url": item.url,
        "primary_source_url": metadata.get("primary_source_url") or item.url,
        "discovery_url": metadata.get("discovery_url"),
        "domain": urlparse(item.url or "").netloc.casefold(),
        "publisher": metadata.get("publisher"),
        "locator": {
            "page": locator.get("page"),
            "section": locator.get("section") or metadata.get("section"),
            "paragraph": locator.get("paragraph"),
            "table_row": locator.get("table_row"),
        },
        "published_at": published_at.isoformat() if published_at else None,
        "updated_at": metadata.get("updated_at"),
        "content_hash": content_hash,
        "retrieved_at": metadata.get("retrieved_at") or utc_now().isoformat(),
        "collection_entrypoint": metadata.get("collection_entrypoint"),
        "attachment_urls": list(metadata.get("attachment_urls") or []),
    }


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
    *,
    allow_text_date_extraction: bool = True,
) -> tuple[list[FetchItem], int]:
    if window_start is None:
        return list(items), 0
    accepted: list[FetchItem] = []
    rejected = 0
    for item in items:
        published_at = _coerce_datetime(item.published_at)
        if published_at is None and allow_text_date_extraction:
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


def _topic_collection_window(
    topic: Topic,
    *,
    now: datetime | None = None,
    requested_start: datetime | None = None,
    requested_end: datetime | None = None,
) -> tuple[datetime | None, datetime]:
    """Resolve the exact ingest window, aligning weekly topics to Beijing weeks."""
    current = _as_aware_utc(now or utc_now()) or utc_now()
    end = _as_aware_utc(requested_end) or current
    if requested_start is not None:
        start = _as_aware_utc(requested_start)
    elif bool(getattr(topic, "weekly_digest_enabled", False)):
        beijing = ZoneInfo("Asia/Shanghai")
        local_end = end.astimezone(beijing)
        monday = local_end.date() - timedelta(days=local_end.weekday())
        start = datetime.combine(
            monday, datetime.min.time(), tzinfo=beijing,
        ).astimezone(timezone.utc)
    else:
        window_days = int(getattr(topic, "collect_window_days", None) or 0)
        start = (
            (end - timedelta(days=window_days)).replace(
                hour=0, minute=0, second=0, microsecond=0,
            )
            if window_days > 0 else None
        )
    if start is not None and start > end:
        raise ValueError("collection window start must not be after end")
    return start, end


def _planning_window_days(
    window_start: datetime | None,
    window_end: datetime | None,
    *,
    fallback_days: int,
) -> int:
    start = _as_aware_utc(window_start)
    end = _as_aware_utc(window_end)
    if start is None or end is None or end <= start:
        return max(1, int(fallback_days or 7))
    return max(1, math.ceil((end - start).total_seconds() / 86_400))


def _planning_window_dates(
    window_start: datetime | None,
    window_end: datetime | None,
) -> tuple[date | None, date | None]:
    start = _as_aware_utc(window_start)
    end = _as_aware_utc(window_end)
    if start is None or end is None or end <= start:
        return None, None
    beijing = ZoneInfo("Asia/Shanghai")
    local_start = start.astimezone(beijing)
    local_end = end.astimezone(beijing)
    end_date = local_end.date()
    if local_end.time() == datetime.min.time():
        end_date -= timedelta(days=1)
    return local_start.date(), end_date


def _topic_review_context(
    topic: Topic,
    semantic_prompt: str | None,
    window_start: datetime | None = None,
    window_end: datetime | None = None,
) -> dict:
    keywords = _topic_collection_keywords(topic)
    context = {
        "topic_id": topic.id,
        "name": topic.name,
        "description": topic.description or "",
        "semantic_instruction": semantic_prompt or topic.description_prompt or "",
        "keywords": [str(value) for value in keywords if value],
        "exclude_keywords": [
            str(value) for value in (topic.exclude_keywords or []) if value
        ],
    }
    return {
        **context,
        **({"collection_window_start": window_start.isoformat()} if window_start else {}),
        **({"collection_window_end": window_end.isoformat()} if window_end else {}),
    }


def _channel_value(source: SourceConfig) -> str:
    return str(getattr(source.channel, "value", source.channel))


_LANGUAGE_LABELS = {
    "zh": "中文",
    "en": "英文",
    "ja": "日文",
    "ko": "韩文",
    "fr": "法文",
    "de": "德文",
    "es": "西班牙文",
    "ru": "俄文",
    "ar": "阿拉伯文",
}


def _language_label(code: str) -> str:
    return _LANGUAGE_LABELS.get(str(code).lower(), str(code))


def _as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _merge_json(existing: dict | None, incoming: dict | None) -> dict:
    base = existing if isinstance(existing, dict) else {}
    extra = incoming if isinstance(incoming, dict) else {}
    return {**base, **extra}
