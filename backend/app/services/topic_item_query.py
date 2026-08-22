"""Canonical topic-membership predicates and aggregates for collected items."""
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Query, Session

from app.models import CollectedItem, ItemTopicMembership


def item_in_topic(topic_id: str):
    """Return a correlated predicate covering primary and secondary membership."""
    membership_exists = select(ItemTopicMembership.item_id).where(and_(
        ItemTopicMembership.item_id == CollectedItem.id,
        ItemTopicMembership.topic_id == topic_id,
    )).exists()
    return or_(CollectedItem.topic_id == topic_id, membership_exists)


def item_has_any_topic():
    """Return a correlated predicate for primary or secondary topic assignment."""
    membership_exists = select(ItemTopicMembership.item_id).where(
        ItemTopicMembership.item_id == CollectedItem.id,
    ).exists()
    return or_(CollectedItem.topic_id.isnot(None), membership_exists)


def filter_items_by_topic(query: Query, topic_id: str | None) -> Query:
    """Apply the canonical topic predicate without introducing duplicate rows."""
    return query.filter(item_in_topic(topic_id)) if topic_id else query


def topic_item_stats(db: Session) -> list[tuple[str, int, Any]]:
    """Count each item once for every topic to which it belongs."""
    primary_pairs = db.query(
        CollectedItem.id.label("item_id"),
        CollectedItem.topic_id.label("topic_id"),
        CollectedItem.collected_at.label("collected_at"),
    ).filter(CollectedItem.topic_id.isnot(None))
    membership_pairs = db.query(
        CollectedItem.id.label("item_id"),
        ItemTopicMembership.topic_id.label("topic_id"),
        CollectedItem.collected_at.label("collected_at"),
    ).join(
        ItemTopicMembership,
        ItemTopicMembership.item_id == CollectedItem.id,
    )
    pairs = primary_pairs.union(membership_pairs).subquery()
    return db.query(
        pairs.c.topic_id,
        func.count(pairs.c.item_id),
        func.max(pairs.c.collected_at),
    ).group_by(pairs.c.topic_id).all()
