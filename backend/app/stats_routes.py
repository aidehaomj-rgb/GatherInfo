"""
Statistics and analytics routes — tag breakdowns, time series, summaries.
"""
from datetime import datetime, timezone
from collections import Counter

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import CollectedItem, CollectionRun, SourceConfig, Tag, Topic

router = APIRouter(prefix="/api/v1", tags=["stats"])


def _now():
    return datetime.now(timezone.utc)


@router.get("/stats/dashboard")
def dashboard(db: Session = Depends(get_db)):
    """One-call dashboard summary."""
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    week_ago = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    from datetime import timedelta
    week_ago = week_ago - timedelta(days=7)

    total_items = db.query(CollectedItem).count()
    items_today = db.query(CollectedItem).filter(CollectedItem.collected_at >= today).count()
    items_this_week = db.query(CollectedItem).filter(CollectedItem.collected_at >= week_ago).count()

    # Category breakdown
    cat_rows = db.query(
        CollectedItem.category, func.count(CollectedItem.id)
    ).group_by(CollectedItem.category).order_by(func.count(CollectedItem.id).desc()).all()

    # Theme results must be derived from the items actually persisted for that
    # topic. Topic.total_items_collected is a lifetime counter and may include
    # entries later removed or deduplicated across sources.
    topic_rows = db.query(
        CollectedItem.topic_id,
        func.count(CollectedItem.id),
        func.max(CollectedItem.collected_at),
    ).filter(CollectedItem.topic_id.isnot(None)).group_by(CollectedItem.topic_id).all()
    topic_counts = {topic_id: (count, latest) for topic_id, count, latest in topic_rows}
    topic_stats = []
    for topic in db.query(Topic).filter(Topic.is_active == True).all():
        count, latest = topic_counts.get(topic.id, (0, None))
        topic_stats.append({
            "topic_id": topic.id,
            "topic_name": topic.name,
            "item_count": count,
            "last_collected_at": latest.isoformat() if latest else None,
        })
    topic_stats.sort(key=lambda row: (row["item_count"], row["last_collected_at"] or ""), reverse=True)

    # Language breakdown
    lang_rows = db.query(
        CollectedItem.language, func.count(CollectedItem.id)
    ).group_by(CollectedItem.language).all()

    # Top tags
    top_tags = db.query(Tag).order_by(Tag.item_count.desc()).limit(15).all()

    # Source health
    source_rows = db.query(
        CollectedItem.source_id,
        func.count(CollectedItem.id),
        func.max(CollectedItem.collected_at),
    ).group_by(CollectedItem.source_id).all()
    source_counts = {source_id: (count, latest) for source_id, count, latest in source_rows}
    sources = db.query(SourceConfig).all()
    source_health = []
    for s in sources:
        last_run = db.query(CollectionRun).filter(
            CollectionRun.source_id == s.id,
            CollectionRun.status.in_(["completed", "partial"]),
        ).order_by(CollectionRun.created_at.desc()).first()
        actual_count, latest_item_at = source_counts.get(s.id, (0, None))
        source_health.append({
            "id": s.id, "name": s.name, "is_active": s.is_active,
            "last_sync_at": (latest_item_at or s.last_sync_at).isoformat() if (latest_item_at or s.last_sync_at) else None,
            "items_collected": actual_count,
            "last_run_status": last_run.status if last_run else None,
        })

    # Recent activity (last 7 days, per day)
    daily_counts = []
    for i in range(7):
        day = _now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
        next_day = day + timedelta(days=1)
        count = db.query(CollectedItem).filter(
            CollectedItem.collected_at >= day,
            CollectedItem.collected_at < next_day,
        ).count()
        daily_counts.append({"date": day.date().isoformat(), "count": count})

    return {
        "summary": {
            "total_items": total_items,
            "items_today": items_today,
            "items_this_week": items_this_week,
            "total_sources": len(sources),
            "active_sources": sum(1 for s in sources if s.is_active),
            "total_topics": db.query(Topic).count(),
            "total_tags": db.query(Tag).count(),
        },
        "categories": [{"category": c or "未分类", "count": n} for c, n in cat_rows],
        "topic_stats": topic_stats,
        "languages": [{"language": l or "unknown", "count": n} for l, n in lang_rows],
        "top_tags": [{"id": t.id, "namespace": t.namespace, "value": t.value, "count": t.item_count}
                     for t in top_tags],
        "source_health": sorted(source_health, key=lambda x: x.get("items_collected", 0), reverse=True),
        "daily_trend": daily_counts[::-1],  # oldest first
    }


@router.get("/stats/items-per-day")
def items_per_day(days: int = Query(default=30, ge=1, le=365), db: Session = Depends(get_db)):
    """Items collected per day for the last N days."""
    from datetime import timedelta
    result = []
    for i in range(days):
        day = _now().replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=i)
        next_day = day + timedelta(days=1)
        count = db.query(CollectedItem).filter(
            CollectedItem.collected_at >= day,
            CollectedItem.collected_at < next_day,
        ).count()
        result.append({"date": day.date().isoformat(), "count": count})
    return result[::-1]


@router.get("/stats/by-category")
def stats_by_category(db: Session = Depends(get_db)):
    rows = db.query(
        CollectedItem.category, func.count(CollectedItem.id)
    ).group_by(CollectedItem.category).order_by(func.count(CollectedItem.id).desc()).all()
    return [{"category": c or "unknown", "count": n} for c, n in rows]


@router.get("/stats/by-language")
def stats_by_language(db: Session = Depends(get_db)):
    rows = db.query(
        CollectedItem.language, func.count(CollectedItem.id)
    ).group_by(CollectedItem.language).order_by(func.count(CollectedItem.id).desc()).all()
    return [{"language": l or "unknown", "count": n} for l, n in rows]


@router.get("/stats/by-source")
def stats_by_source(db: Session = Depends(get_db)):
    rows = db.query(
        CollectedItem.source_id, func.count(CollectedItem.id)
    ).group_by(CollectedItem.source_id).order_by(func.count(CollectedItem.id).desc()).all()
    return [{"source_id": s or "unknown", "count": n} for s, n in rows]


@router.get("/stats/by-tag-namespace")
def stats_by_tag_namespace(db: Session = Depends(get_db)):
    rows = db.query(
        Tag.namespace, func.count(Tag.id), func.sum(Tag.item_count)
    ).group_by(Tag.namespace).all()
    return [{"namespace": ns, "tag_count": tc, "total_items": ti or 0} for ns, tc, ti in rows]
