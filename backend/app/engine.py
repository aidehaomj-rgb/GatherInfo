"""
Collection Engine — the central orchestrator.

Flow:
    Topic → keywords → sources → connectors → FetchItems
    → dedup → persist (with topic_id) → auto-tag → return stats
"""
import asyncio
import logging
import re
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from sqlalchemy.orm import Session

from app.connectors.base import ConnectorRegistry, CollectResult, FetchItem
from app.content_parser import parse_fetch_item
from app.models import (
    CollectionRun, CollectedItem, ItemStatus,
    JobStatus, ModelConfig, SourceConfig, Tag, Topic,
)

logger = logging.getLogger(__name__)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class CollectionEngine:
    def __init__(self, db: Session):
        self.db = db

    # ── Single source collection ────────────────────────────────────────

    async def collect_from_source(
        self, source_id: str, keywords: list[str], topic_id: str | None = None,
        window_start: "datetime | None" = None, window_end: "datetime | None" = None,
        batch_id: str | None = None, model: ModelConfig | None = None,
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

        try:
            connector = ConnectorRegistry.create(source)
        except ValueError as exc:
            run.status = JobStatus.FAILED
            run.error_log = [str(exc)]
            self.db.commit()
            return CollectResult(run_id=run.id, source_id=source.id,
                                 status=JobStatus.FAILED, items=[], error_log=[str(exc)])

        result = await connector.execute(run, keywords)
        # Add Chinese translations for non-Chinese items before storing.
        # The original title/content are preserved; translations live in raw_metadata.
        if result.items:
            try:
                from app.translation_service import translate_fetch_items_to_metadata
                await translate_fetch_items_to_metadata(result.items, model or _web_translation_model())
            except Exception as exc:
                logger.warning("Item translation failed (non-blocking): %s", exc)
        self._persist_items(
            result.items, source.id, run.id, topic_id, window_start, window_end, keywords
        )
        self._update_source(source, len(result.items))
        self.db.commit()
        return result

    # ── Topic-driven collection ─────────────────────────────────────────

    async def collect_topic(self, topic_id: str) -> list[CollectResult]:
        """Collect from all sources relevant to a topic."""
        topic = self.db.query(Topic).filter(Topic.id == topic_id).first()
        if not topic:
            raise ValueError(f"Topic not found: {topic_id}")

        sources = self._resolve_sources(topic)
        source_ids = [s.id for s in sources]
        keywords = topic.keywords if isinstance(topic.keywords, list) else [topic.keywords]

        # Compute the publication time window from the topic configuration.
        # window_days <= 0 disables filtering (collect everything).
        window_days = getattr(topic, "collect_window_days", None) or 0
        window_end = utc_now()
        window_start = window_end - timedelta(days=window_days) if window_days > 0 else None

        # Generate a shared batch_id for all runs in this topic collection
        from uuid import uuid4
        batch_id = f"batch-{uuid4().hex[:12]}"

        # Load default model for item translation
        default_model = self.db.query(ModelConfig).filter(
            ModelConfig.is_default == True, ModelConfig.is_active == True
        ).first()

        # Parallel collection — topic_id flows through into runs and items
        tasks = [
            self.collect_from_source(sid, keywords, topic.id, window_start, window_end, batch_id, default_model)
            for sid in source_ids
        ]
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

    def ensure_tag(self, tag_id: str, namespace: str, value: str, label: str | None = None) -> Tag:
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
            return self.db.query(SourceConfig).filter(
                SourceConfig.id.in_(topic.source_ids),
                SourceConfig.is_active == True,
            ).all()
        return self.db.query(SourceConfig).filter(SourceConfig.is_active == True).all()

    async def _translate_fetch_items(self, items: list[FetchItem], model: ModelConfig) -> list[FetchItem] | None:
        """Backward-compatible wrapper: attach translations without replacing originals."""
        from app.translation_service import translate_fetch_items_to_metadata
        await translate_fetch_items_to_metadata(items, model)
        return items

    def _persist_items(self, items: list[FetchItem], source_id: str, run_id: str,
                       topic_id: str | None = None, window_start: "datetime | None" = None,
                       window_end: "datetime | None" = None,
                       keywords: list[str] | None = None):
        for fi in items:
            parsed = parse_fetch_item(fi)
            if not parsed.is_meaningful:
                continue

            pub = _coerce_datetime(fi.published_at)

            # Strictly enforce the configured time window. If a topic has a window
            # and the item has no usable publication date, we skip it so that old
            # or undated content does not pollute the collection.
            if window_start is not None:
                if pub is None:
                    pub = _extract_date_from_text(f"{fi.title} {fi.content or ''} {fi.summary or ''}")
                if pub is None or _is_out_of_range(pub, window_start, window_end):
                    continue

            # Keyword relevance filtering: skip items that don't match the keyword combination
            # Keywords work together as a topic definition, not individually.
            if keywords:
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
            try:
                existing = self.db.query(CollectedItem).filter(CollectedItem.id == item_id).first()
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
                        content_hash=_hash(parsed.content or fi.title),
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
                self.db.flush()
            except Exception:
                self.db.rollback()
        self.db.commit()

    def _update_source(self, source: SourceConfig, items_found: int):
        source.last_sync_at = utc_now()
        source.items_collected += items_found


def _hash(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode()).hexdigest()


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


def _as_aware_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _merge_json(existing: dict | None, incoming: dict | None) -> dict:
    base = existing if isinstance(existing, dict) else {}
    extra = incoming if isinstance(incoming, dict) else {}
    return {**base, **extra}
