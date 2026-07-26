"""Tag business logic — query, merge, stats, ensure."""
import logging
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Tag, item_tags

logger = logging.getLogger(__name__)


def refresh_tag_counts(db: Session, tag_ids: list[str] | None = None) -> None:
    """Synchronize cached tag counts from the item-tag association table."""
    counts_query = db.query(item_tags.c.tag_id, func.count(item_tags.c.item_id))
    if tag_ids:
        counts_query = counts_query.filter(item_tags.c.tag_id.in_(tag_ids))
    counts = dict(counts_query.group_by(item_tags.c.tag_id).all())

    tags_query = db.query(Tag)
    if tag_ids:
        tags_query = tags_query.filter(Tag.id.in_(tag_ids))
    for tag in tags_query.all():
        tag.item_count = int(counts.get(tag.id, 0))
    db.commit()


def list_tags(
    db: Session,
    namespace: Optional[str] = None,
    sort_by: str = "item_count",
    limit: int = 100,
):
    """List tags with optional namespace filter and sorting."""
    refresh_tag_counts(db)
    q = db.query(Tag)
    if namespace:
        q = q.filter(Tag.namespace == namespace)
    if sort_by == "item_count":
        q = q.order_by(Tag.item_count.desc())
    elif sort_by == "recent":
        q = q.order_by(Tag.last_seen_at.desc().nullslast())
    else:
        q = q.order_by(Tag.value.asc())
    return q.limit(limit).all()


def ensure_tag(db: Session, namespace: str, value: str, color: Optional[str] = None) -> Tag:
    """Get or create a tag. Atomically updates item_count on existing tags."""
    tag_id = f"tag-{namespace}-{value}".lower().replace(" ", "-")[:80]
    tag = db.query(Tag).filter(Tag.id == tag_id).first()
    if not tag:
        tag = Tag(id=tag_id, namespace=namespace, value=value, label=value, color=color)
        db.add(tag)
        db.flush()
    return tag


def update_tag(db: Session, tag_id: str, data: dict) -> Tag:
    """Update tag fields."""
    t = db.query(Tag).filter(Tag.id == tag_id).first()
    if not t:
        raise HTTPException(404, f"Tag not found: {tag_id}")
    for k, v in data.items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t


def delete_tag(db: Session, tag_id: str) -> None:
    """Delete a tag and its item associations."""
    t = db.query(Tag).filter(Tag.id == tag_id).first()
    if not t:
        raise HTTPException(404, f"Tag not found: {tag_id}")
    db.delete(t)
    db.commit()


def merge_tags(db: Session, source_tag_id: str, target_tag_id: str) -> dict:
    """Merge source tag into target: move item associations, delete source."""
    if source_tag_id == target_tag_id:
        raise HTTPException(400, "源标签与目标标签不能相同")

    source = db.query(Tag).filter(Tag.id == source_tag_id).first()
    target = db.query(Tag).filter(Tag.id == target_tag_id).first()
    if not source:
        raise HTTPException(404, f"源标签不存在: {source_tag_id}")
    if not target:
        raise HTTPException(404, f"目标标签不存在: {target_tag_id}")

    try:
        target_item_ids = {
            row[0] for row in db.query(item_tags.c.item_id)
            .filter(item_tags.c.tag_id == target.id).all()
        }
        source_links = db.query(item_tags.c.item_id).filter(item_tags.c.tag_id == source.id).all()
        moved = 0
        for (item_id,) in source_links:
            if item_id in target_item_ids:
                continue
            db.execute(item_tags.insert().values(item_id=item_id, tag_id=target.id))
            target_item_ids.add(item_id)
            moved += 1
        db.execute(item_tags.delete().where(item_tags.c.tag_id == source.id))
        db.expire_all()
        deleted_id = source.id
        db.delete(source)
        target.item_count = db.query(item_tags.c.item_id).filter(
            item_tags.c.tag_id == target.id
        ).count()
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.error("merge_tags failed: %s", exc)
        raise HTTPException(500, f"标签合并失败: {exc}")

    return {"target_tag_id": target.id, "moved_items": moved, "deleted_tag_id": deleted_id}


def tag_stats(db: Session, limit: int = 50) -> list[dict]:
    """Compute per-tag distribution stats (categories, languages, sources)."""
    from app.collection_schemas import TagStatsOut

    refresh_tag_counts(db)
    tags = db.query(Tag).order_by(Tag.item_count.desc()).limit(limit).all()
    result = []
    for tag in tags:
        items = tag.items
        cats: dict[str, int] = {}
        langs: dict[str, int] = {}
        srcs: dict[str, int] = {}
        for it in items:
            if it.category:
                cats[it.category] = cats.get(it.category, 0) + 1
            if it.language:
                langs[it.language] = langs.get(it.language, 0) + 1
            if it.source_id:
                srcs[it.source_id] = srcs.get(it.source_id, 0) + 1
        result.append(TagStatsOut(
            tag_id=tag.id, namespace=tag.namespace, value=tag.value,
            item_count=tag.item_count, last_seen_at=tag.last_seen_at,
            categories=cats, languages=langs, sources=srcs,
        ))
    return result
