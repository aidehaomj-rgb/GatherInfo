"""Item business logic — queries, filtering, batch operations."""
import logging
from sqlalchemy.orm import Session
from sqlalchemy import text
from fastapi import HTTPException

from app.models import CollectedItem, CollectionRun, Tag
from app.services.topic_item_query import filter_items_by_topic

logger = logging.getLogger(__name__)


# research 系列表直接引用 collected_items.id 且未声明 ON DELETE CASCADE。
# SQLite 连接启用了 PRAGMA foreign_keys=ON，删除条目前必须先清理这些引用，
# 否则会触发 FOREIGN KEY constraint failed。
_ITEM_REF_TABLES = (
    ("research_evidence", "item_id"),
    ("research_case_entities", "source_item_id"),
    ("research_cases", "primary_item_id"),
)


def purge_item_references(db: Session, item_ids: list[str]) -> None:
    """删除 research 相关表对目标 item 的外键引用，避免删除条目时外键失败。

    item_tags / item_topic_memberships 已声明 ON DELETE CASCADE，由数据库层
    自动级联，无需在此处理。
    """
    if not item_ids:
        return
    chunk = 200
    for table, column in _ITEM_REF_TABLES:
        for i in range(0, len(item_ids), chunk):
            ids = item_ids[i:i + chunk]
            placeholders = ", ".join(f":id_{j}" for j in range(len(ids)))
            params = {f"id_{j}": ids[j] for j in range(len(ids))}
            db.execute(
                text(f"DELETE FROM {table} WHERE {column} IN ({placeholders})"),
                params,
            )


def build_item_query(
    db: Session,
    topic_id: str | None = None,
    source_id: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    status: str | None = None,
    language: str | None = None,
    run_id: str | None = None,
    batch_id: str | None = None,
    q: str | None = None,
):
    """Build a filtered query for CollectedItem, reusable across list/export/ids."""
    query = db.query(CollectedItem)
    query = filter_items_by_topic(query, topic_id)
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
        tag_ids = [tag_id.strip() for tag_id in tag.split(",") if tag_id.strip()]
        for tag_id in tag_ids:
            query = query.filter(CollectedItem.tags.any(Tag.id == tag_id))
    if q:
        query = query.filter(
            (CollectedItem.title.ilike(f"%{q}%")) |
            (CollectedItem.content.ilike(f"%{q}%"))
        )
    return query


def list_items(
    db: Session,
    page: int = 1, page_size: int = 20,
    **filters,
):
    """List items with pagination."""
    query = build_item_query(db, **filters)
    total = query.count()
    items = query.order_by(CollectedItem.collected_at.desc())         .offset((page - 1) * page_size)         .limit(page_size)         .all()
    return items, total


def get_item_ids(db: Session, **filters) -> tuple[list[str], int]:
    """Get matching item IDs (for batch-select)."""
    query = build_item_query(db, **filters).with_entities(CollectedItem.id)
    total = query.count()
    ids = [row[0] for row in query.all()]
    return ids, total


def batch_delete_items(db: Session, item_ids: list[str]) -> int:
    """Delete items by ID list. Returns count of deleted items."""
    if not item_ids:
        return 0
    purge_item_references(db, item_ids)
    deleted = 0
    for item_id in item_ids:
        item = db.query(CollectedItem).filter(CollectedItem.id == item_id).first()
        if item:
            db.delete(item)
            deleted += 1
    db.commit()
    return deleted


def get_item(db: Session, item_id: str) -> CollectedItem:
    """Get a single item by ID."""
    it = db.query(CollectedItem).filter(CollectedItem.id == item_id).first()
    if not it:
        raise HTTPException(404, f"Item not found: {item_id}")
    return it
