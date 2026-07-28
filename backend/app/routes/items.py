"""Items, Runs, Batches — queries, history, delete."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.collection_schemas import (
    ActiveRunOut, BatchOut, BatchRunOut, RunFailureOut, ItemInventoryOut,
    ItemDeleteRequest, ItemListOut, ItemOut, ItemQualityReviewRequest, ItemTranslateRequest,
    RunOut,
)
from app.database import get_db
from app.models import (
    Category, CollectedItem, CollectionRun, JobStatus, ModelConfig,
    SourceConfig, Tag, Topic,
)

from ._helpers import _item_tags
from app.translation_service import item_translation_fields, translate_existing_items
from app.engine import _web_translation_model

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["items"])


# ── Runs ────────────────────────────────────────────────────────────────

@router.get("/runs", response_model=list[RunOut])
def list_runs(
    topic_id: str | None = None,
    source_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(CollectionRun)
    if topic_id:
        q = q.filter(CollectionRun.topic_id == topic_id)
    if source_id:
        q = q.filter(CollectionRun.source_id == source_id)
    return q.order_by(CollectionRun.created_at.desc()).limit(limit).all()


# ── Batches / History ───────────────────────────────────────────────────

@router.get("/runs/batches", response_model=list[BatchOut])
def list_batches(
    topic_id: str | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(CollectionRun).filter(CollectionRun.created_at.isnot(None))
    if topic_id:
        q = q.filter(CollectionRun.topic_id == topic_id)
    q = q.order_by(CollectionRun.created_at.desc()).limit(limit * 5).all()

    batch_map: dict[str, list] = {}
    for r in q:
        bid = getattr(r, 'batch_id', None)
        if bid:
            if bid not in batch_map:
                batch_map[bid] = []
            batch_map[bid].append(r)

    batches: list[BatchOut] = []
    for batch_id, runs in sorted(
        batch_map.items(),
        key=lambda x: max((r.created_at for r in x[1] if r.created_at), default=None) or datetime.min,
        reverse=True,
    )[:limit]:
        runs.sort(key=lambda r: r.source_id or "")
        if not runs:
            continue

        topic = None
        if runs[0].topic_id:
            topic = db.query(Topic).filter(Topic.id == runs[0].topic_id).first()

        started_at = min((r.created_at for r in runs if r.created_at), default=None)
        completed_at = max((r.completed_at for r in runs if r.completed_at), default=None)

        run_outs: list[BatchRunOut] = []
        for r in runs:
            src = db.query(SourceConfig).filter(SourceConfig.id == r.source_id).first()
            run_outs.append(BatchRunOut(
                id=r.id, source_id=r.source_id,
                topic_id=r.topic_id, status=r.status if r.status else "unknown",
                items_new=r.items_new or 0, items_found=r.items_found or 0,
                items_failed=r.items_failed or 0,
                started_at=r.started_at.isoformat() if r.started_at else None,
                completed_at=r.completed_at.isoformat() if r.completed_at else None,
                duration_ms=r.duration_ms,
                error_log=r.error_log,
                source_name=src.name if src else r.source_id,
            ))

        error_count = sum(1 for r in runs if r.status and r.status == "failed")
        has_running = any(r.status and r.status in ("running", "pending") for r in runs)
        status = "running" if has_running else (
            "partial" if 0 < error_count < len(runs) else (
                "failed" if error_count == len(runs) else "completed"
            )
        )

        batch_label = None
        if topic:
            ts = started_at.strftime("%Y-%m-%d %H:%M") if started_at else ""
            batch_label = f"{topic.name}_{ts}"
        elif runs[0].source_id:
            ts = started_at.strftime("%Y-%m-%d %H:%M") if started_at else ""
            batch_label = f"{runs[0].source_id}_{ts}"

        current_item_count = db.query(CollectedItem).filter(
            CollectedItem.run_id.in_([run.id for run in runs]),
        ).count()
        batches.append(BatchOut(
            batch_id=batch_id,
            topic_id=runs[0].topic_id,
            topic_name=topic.name if topic else None,
            batch_label=batch_label,
            status=status,
            total_items=current_item_count,
            total_new=sum(r.items_new or 0 for r in runs),
            started_at=started_at.isoformat() if started_at else None,
            completed_at=completed_at.isoformat() if completed_at else None,
            source_count=len(runs),
            runs=run_outs,
        ))

    return batches


@router.get("/runs/active", response_model=list[ActiveRunOut])
def list_active_runs(db: Session = Depends(get_db)):
    runs = db.query(CollectionRun).filter(
        CollectionRun.status.in_([JobStatus.RUNNING, JobStatus.PENDING]),
    ).order_by(CollectionRun.created_at.desc()).limit(20).all()

    batch_ids = {run.batch_id for run in runs if run.batch_id}
    batch_metrics: dict[str, dict[str, int]] = {}
    if batch_ids:
        batch_runs = db.query(CollectionRun).filter(CollectionRun.batch_id.in_(batch_ids)).all()
        for batch_id in batch_ids:
            grouped = [run for run in batch_runs if run.batch_id == batch_id]
            statuses = [str(run.status or "").lower() for run in grouped]
            batch_metrics[batch_id] = {
                "total": len(grouped),
                "completed": sum(status in ("completed", "partial") for status in statuses),
                "failed": sum(status == "failed" for status in statuses),
                "active": sum(status in ("running", "pending") for status in statuses),
            }

    result: list[ActiveRunOut] = []
    for r in runs:
        src = db.query(SourceConfig).filter(SourceConfig.id == r.source_id).first()
        topic = db.query(Topic).filter(Topic.id == r.topic_id).first() if r.topic_id else None
        duration = None
        if r.started_at and not r.completed_at:
            started = r.started_at
            if hasattr(started, 'tzinfo') and started.tzinfo is None:
                started = started.replace(tzinfo=timezone.utc)
            duration = int((datetime.now(timezone.utc) - started).total_seconds())

        metrics = batch_metrics.get(r.batch_id or "", {
            "total": 1, "completed": 0, "failed": 0, "active": 1,
        })
        result.append(ActiveRunOut(
            id=r.id, source_id=r.source_id,
            source_name=src.name if src else r.source_id,
            topic_id=r.topic_id,
            topic_name=topic.name if topic else None,
            status=r.status if r.status else "unknown",
            keywords_used=r.keywords_used or [],
            items_found=r.items_found or 0,
            items_new=r.items_new or 0,
            started_at=r.started_at.isoformat() if r.started_at else None,
            duration_seconds=duration,
            batch_id=getattr(r, 'batch_id', None),
            progress_events=getattr(r, 'progress_events', None) or [],
            batch_total_sources=metrics["total"],
            batch_completed_sources=metrics["completed"],
            batch_failed_sources=metrics["failed"],
            batch_active_sources=metrics["active"],
        ))

    return result


@router.get("/runs/failures", response_model=list[RunFailureOut])
def list_run_failures(
    batch_ids: str = Query(min_length=1, max_length=2000),
    db: Session = Depends(get_db),
):
    requested_ids = [value.strip() for value in batch_ids.split(",") if value.strip()]
    if not requested_ids:
        return []
    runs = db.query(CollectionRun).filter(
        CollectionRun.batch_id.in_(requested_ids),
        CollectionRun.status == JobStatus.FAILED,
    ).order_by(CollectionRun.created_at.desc()).all()
    if not runs:
        return []

    source_ids = [run.source_id for run in runs]
    recurring = dict(db.query(CollectionRun.source_id, func.count(CollectionRun.id)).filter(
        CollectionRun.source_id.in_(source_ids),
        CollectionRun.status == JobStatus.FAILED,
    ).group_by(CollectionRun.source_id).all())
    sources = {
        source.id: source for source in db.query(SourceConfig).filter(SourceConfig.id.in_(source_ids)).all()
    }
    return [_failure_out(run, sources.get(run.source_id), int(recurring.get(run.source_id, 1))) for run in runs]


def _failure_out(run: CollectionRun, source: SourceConfig | None, recurring_failures: int) -> RunFailureOut:
    errors = [str(value) for value in (run.error_log or []) if str(value).strip()]
    category, repairable, recommendation, action = _failure_guidance(errors, recurring_failures)
    channel = source.channel.value if source and hasattr(source.channel, "value") else str(source.channel if source else "unknown")
    return RunFailureOut(
        run_id=run.id,
        batch_id=run.batch_id,
        source_id=run.source_id,
        source_name=source.name if source else run.source_id,
        source_channel=channel,
        errors=errors or ["未记录具体错误，请重新验证该信息源。"],
        category=category,
        repairable=repairable,
        recurring_failures=recurring_failures,
        recommendation=recommendation,
        suggested_action=action,
    )


def _failure_guidance(errors: list[str], recurring_failures: int) -> tuple[str, bool, str, str]:
    detail = " ".join(errors).lower()
    if "api_key" in detail or "authentication" in detail or "unauthorized" in detail:
        return "credentials", True, "该渠道缺少或拒绝 API Key。请在信息源配置中更新密钥后重新验证。", "edit_source"
    if "403" in detail or "406" in detail or "forbidden" in detail or "not acceptable" in detail:
        return "access_restricted", True, "目标站拒绝当前访问方式。请改用官方 RSS、允许的 API，或将其改为网页抓取后验证。", "edit_source"
    if "404" in detail or "not found" in detail:
        action = "delete_candidate" if recurring_failures >= 3 else "edit_source"
        ending = "连续多次返回 404；如无法找到新的官方入口，建议删除该信息源。" if action == "delete_candidate" else "请更新为有效的 RSS 或网页地址后重新验证。"
        return "endpoint_missing", True, ending, action
    if "xml parse" in detail or "not well-formed" in detail or "undefined entity" in detail:
        return "feed_format", True, "地址返回的不是兼容 RSS/Atom。请更换有效订阅地址，或改为网页抓取渠道。", "edit_source"
    if "certificate" in detail or "ssl" in detail:
        return "tls", True, "站点证书校验失败。请先核验站点证书和地址；不建议关闭证书校验。", "edit_source"
    if "base_url not configured" in detail:
        return "address_missing", True, "信息源缺少采集地址。请填写网页、RSS 或 API 地址后重新验证。", "edit_source"
    return "network_or_provider", False, "请重新验证该信息源；若连续失败且没有替代入口，建议停用或删除。", "disable_candidate"


@router.post("/runs/{run_id}/stop")
def stop_run(run_id: str, db: Session = Depends(get_db)):
    run = db.query(CollectionRun).filter(CollectionRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status not in (JobStatus.RUNNING, JobStatus.PENDING, "running", "pending"):
        return {"id": run.id, "status": run.status, "message": "Run is not active"}

    now = datetime.now(timezone.utc)
    started = run.started_at
    if started and getattr(started, "tzinfo", None) is None:
        started = started.replace(tzinfo=timezone.utc)
    run.status = JobStatus.FAILED
    run.completed_at = now
    run.duration_ms = int((now - started).total_seconds() * 1000) if started else None
    errors = list(run.error_log or [])
    errors.append("Stopped manually from UI; previous collection did not complete.")
    run.error_log = errors
    db.commit()
    return {"id": run.id, "status": run.status, "message": "Run stopped"}


# ── Items ───────────────────────────────────────────────────────────────

@router.get("/items", response_model=ItemListOut)
def list_items(
    topic_id: str | None = None,
    source_id: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    language: str | None = None,
    run_id: str | None = None,
    batch_id: str | None = None,
    q: str | None = Query(default=None, description="Full-text search in title/content"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(CollectedItem)

    if topic_id:
        query = query.filter(CollectedItem.topic_id == topic_id)
    if source_id:
        query = query.filter(CollectedItem.source_id == source_id)
    if category:
        query = query.filter(CollectedItem.category == category)
    if status:
        query = query.filter(CollectedItem.status == status)
    if language:
        query = query.filter(CollectedItem.language == language)
    if run_id:
        query = query.filter(CollectedItem.run_id == run_id)
    if batch_id:
        query = query.filter(CollectedItem.run_id.in_(
            db.query(CollectionRun.id).filter(CollectionRun.batch_id == batch_id),
        ))
    if tag:
        query = query.filter(CollectedItem.tags.any(Tag.id == tag))
    if q:
        needle = q.lower()
        candidates = query.order_by(
            CollectedItem.collected_at.desc(), CollectedItem.published_at.desc()
        ).all()
        filtered = [it for it in candidates if _matches_item_query(it, needle)]
        total = len(filtered)
        items = filtered[(page - 1) * page_size: page * page_size]
    else:
        total = query.count()
        items = (
            query.order_by(CollectedItem.collected_at.desc(), CollectedItem.published_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

    return ItemListOut(
        items=[_item_out(it) for it in items],
        total=total, page=page, page_size=page_size,
    )


@router.get("/items/inventory", response_model=ItemInventoryOut)
def item_inventory(db: Session = Depends(get_db)):
    """Return a live inventory built only from currently persisted items."""
    now = datetime.now(timezone.utc)

    def grouped_rows(column, labels: dict[str, str], fallback_id: str, fallback_label: str):
        rows = db.query(
            column, func.count(CollectedItem.id), func.max(CollectedItem.collected_at),
        ).group_by(column).all()
        result = []
        for value, count, latest_at in rows:
            key = str(value) if value else fallback_id
            label = labels.get(key, str(value) if value else fallback_label)
            result.append({"id": key, "label": label, "count": int(count), "latest_at": latest_at})
        return sorted(result, key=lambda row: (-row["count"], row["label"]))

    topic_names = dict(db.query(Topic.id, Topic.name).all())
    source_names = dict(db.query(SourceConfig.id, SourceConfig.name).all())
    topics = grouped_rows(CollectedItem.topic_id, topic_names, "__unassigned__", "未关联主题")
    for row in topics:
        row["topic_id"] = row["id"] if row["id"] != "__unassigned__" else None

    categories = grouped_rows(
        CollectedItem.category, {}, "__uncategorized__", "未分类",
    )
    sources = grouped_rows(CollectedItem.source_id, source_names, "__unknown_source__", "未知信息源")
    statuses = grouped_rows(CollectedItem.status, {}, "__unknown_status__", "未知状态")

    batch_rows = db.query(
        CollectionRun.batch_id,
        CollectionRun.topic_id,
        func.count(CollectedItem.id),
        func.max(CollectedItem.collected_at),
    ).join(
        CollectedItem, CollectedItem.run_id == CollectionRun.id,
    ).filter(
        CollectionRun.batch_id.isnot(None),
    ).group_by(CollectionRun.batch_id, CollectionRun.topic_id).all()
    batches = []
    for batch_id, topic_id, count, latest_at in batch_rows:
        label = topic_names.get(topic_id, topic_id or "未关联主题")
        batches.append({
            "id": batch_id,
            "label": f"{label} · {batch_id}",
            "count": int(count),
            "latest_at": latest_at,
            "topic_id": topic_id,
        })
    min_utc = datetime.min.replace(tzinfo=timezone.utc)
    batches.sort(key=lambda row: row["latest_at"] or min_utc, reverse=True)

    return ItemInventoryOut(
        total_items=db.query(CollectedItem).count(),
        topics=topics,
        categories=categories,
        batches=batches,
        sources=sources,
        statuses=statuses,
        generated_at=now,
    )


@router.get("/items/featured", response_model=list[ItemOut])
def list_featured_items(db: Session = Depends(get_db)):
    from app.services.featured_intelligence import get_featured_items

    return [_item_out(item) for item in get_featured_items(db)]


def _item_out(it: CollectedItem) -> ItemOut:
    return ItemOut(
        id=it.id, source_id=it.source_id, run_id=it.run_id,
        title=it.title, content=it.content, summary=it.summary, url=it.url,
        **item_translation_fields(it),
        enforcement_review=(it.raw_metadata or {}).get("enforcement_review") if isinstance(it.raw_metadata, dict) else None,
        quality_review=(it.raw_metadata or {}).get("quality_review") if isinstance(it.raw_metadata, dict) else None,
        language=it.language, category=it.category, tags=_item_tags(it),
        entities=it.entities,
        quality_score=it.quality_score or 0,
        relevance_score=it.relevance_score or 0,
        status=it.status if it.status else "raw",
        collected_at=it.collected_at, published_at=it.published_at,
    )


def _matches_item_query(item: CollectedItem, needle: str) -> bool:
    trans = item_translation_fields(item)
    haystack = " ".join([
        item.title or "",
        item.summary or "",
        item.content or "",
        trans.get("title_zh") or "",
        trans.get("summary_zh") or "",
        trans.get("content_zh") or "",
    ]).lower()
    return needle in haystack


@router.post("/items/translate")
async def translate_items(
    data: ItemTranslateRequest | None = None,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    from app.model_defaults import get_default_model
    model = get_default_model(db)
    item_ids = data.item_ids if data and data.item_ids else None
    return await translate_existing_items(
        db,
        model or _web_translation_model(),
        limit=len(item_ids) if item_ids else limit,
        item_ids=item_ids,
    )


@router.post("/items/quality-review")
async def quality_review_items(
    data: ItemQualityReviewRequest,
    db: Session = Depends(get_db),
):
    """Curate historical entries and remove low-value, non-article pages."""
    from app.content_quality import review_persisted_items

    from app.model_defaults import get_default_model
    model = get_default_model(db)
    return await review_persisted_items(
        db, model, item_ids=data.item_ids or None, limit=data.limit,
    )


@router.get("/items/ids")
def list_item_ids(
    topic_id: str | None = None,
    source_id: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    language: str | None = None,
    run_id: str | None = None,
    batch_id: str | None = None,
    q: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    from app.services.item_service import get_item_ids
    ids, total = get_item_ids(
        db,
        topic_id=topic_id, source_id=source_id, category=category,
        tag=tag, status=status, language=language, run_id=run_id, batch_id=batch_id, q=q,
    )
    return {"ids": ids, "total": total, "matching": len(ids)}

# ── Export ────────────────────────────────────────────────────────────────

@router.get("/items/export")
def export_items(
    format: str = Query(default="csv", description="csv | json | xlsx"),
    topic_id: str | None = None,
    source_id: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    language: str | None = None,
    q: str | None = None,
    limit: int = Query(default=10000, ge=1, le=50000),
    db: Session = Depends(get_db),
):
    """Export items matching the given filters."""
    from app.routes.export_routes import _export_csv, _export_json, _export_xlsx
    from app.services.item_service import build_item_query
    query = build_item_query(
        db, topic_id=topic_id, source_id=source_id, category=category,
        tag=tag, language=language, q=q,
    )
    items = query.order_by(CollectedItem.collected_at.desc()).limit(limit).all()
    if format == "csv":
        return _export_csv(items)
    elif format == "json":
        return _export_json(items)
    elif format == "xlsx":
        return _export_xlsx(items)
    else:
        raise HTTPException(400, f"Unsupported format: {format}. Use csv, json, or xlsx.")

# ── FTS Search ───────────────────────────────────────────────────────────

@router.get("/items/search", response_model=ItemListOut)
def search_items(
    q: str = Query(default=..., description="Search query with optional title:/content: syntax"),
    topic_id: str | None = None,
    source_id: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    """Full-text search using SQLite FTS5 with optional field filters."""
    try:
        from app import fts_search
        item_ids, total = fts_search.search_items(
            db, q, topic_id=topic_id, source_id=source_id,
            limit=page_size, offset=(page - 1) * page_size,
        )
    except Exception as exc:
        logger.warning("FTS search failed, falling back to LIKE: %s", exc)
        # Fallback handled inside fts_search.search_items
        return list_items(topic_id=topic_id, source_id=source_id, q=q,
                          page=page, page_size=page_size, db=db)

    if not item_ids:
        return ItemListOut(items=[], total=0, page=page, page_size=page_size)

    items = db.query(CollectedItem).filter(
        CollectedItem.id.in_(item_ids)
    ).order_by(CollectedItem.collected_at.desc()).all()

    return ItemListOut(
        items=[ItemOut(
            id=it.id, source_id=it.source_id, run_id=it.run_id,
            title=it.title, content=it.content, summary=it.summary, url=it.url,
            **item_translation_fields(it),
            enforcement_review=(it.raw_metadata or {}).get("enforcement_review") if isinstance(it.raw_metadata, dict) else None,
            quality_review=(it.raw_metadata or {}).get("quality_review") if isinstance(it.raw_metadata, dict) else None,
            language=it.language, category=it.category, tags=_item_tags(it),
            entities=it.entities,
            quality_score=it.quality_score or 0,
            relevance_score=it.relevance_score or 0,
            status=it.status if it.status else "raw",
            collected_at=it.collected_at, published_at=it.published_at,
        ) for it in items],
        total=total, page=page, page_size=page_size,
    )

@router.get("/items/{item_id}", response_model=ItemOut)
def get_item(item_id: str, db: Session = Depends(get_db)):
    from app.services.item_service import get_item as _get_item
    it = _get_item(db, item_id)
    return ItemOut(
        id=it.id, source_id=it.source_id, run_id=it.run_id,
        title=it.title, content=it.content, summary=it.summary, url=it.url,
        **item_translation_fields(it),
        enforcement_review=(it.raw_metadata or {}).get("enforcement_review") if isinstance(it.raw_metadata, dict) else None,
        quality_review=(it.raw_metadata or {}).get("quality_review") if isinstance(it.raw_metadata, dict) else None,
        language=it.language, category=it.category, tags=_item_tags(it),
        entities=it.entities,
        quality_score=it.quality_score or 0,
        relevance_score=it.relevance_score or 0,
        status=it.status if it.status else "raw",
        collected_at=it.collected_at, published_at=it.published_at,
    )


@router.post("/items/batch-delete")
def batch_delete_items(data: ItemDeleteRequest, db: Session = Depends(get_db)):
    from app.services.item_service import batch_delete_items as _batch_delete
    deleted = _batch_delete(db, data.item_ids)
    return {"deleted": deleted, "total": len(data.item_ids)}
