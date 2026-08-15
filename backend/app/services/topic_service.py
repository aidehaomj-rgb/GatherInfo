"""Topic business logic."""
import logging
import re
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models import Topic

logger = logging.getLogger(__name__)


def _normalize_keywords(keywords: list[str]) -> list[str]:
    """Normalize keyword punctuation and whitespace."""
    result = []
    for kw in keywords:
        if not kw or not kw.strip():
            continue
        parts = re.split(r"[,，;；、]", kw.replace("：", ":"))
        result.extend(part.strip() for part in parts if part.strip())
    return result


def create_topic(db: Session, data: dict) -> Topic:
    """Create a new topic with normalized keywords."""
    from uuid import uuid4
    topic_id = data.get("id") or f"topic-{uuid4().hex[:8]}"
    if db.query(Topic).filter(Topic.id == topic_id).first():
        raise HTTPException(400, f"Topic '{topic_id}' already exists")

    payload = {k: v for k, v in data.items() if k != "id"}
    if "keywords" in payload:
        payload["keywords"] = _normalize_keywords(payload["keywords"])

    t = Topic(id=topic_id, **payload)
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def update_topic(db: Session, topic_id: str, data: dict) -> Topic:
    """Update an existing topic."""
    t = db.query(Topic).filter(Topic.id == topic_id).first()
    if not t:
        raise HTTPException(404, f"Topic not found: {topic_id}")
    if "keywords" in data:
        data["keywords"] = _normalize_keywords(data["keywords"])
    for k, v in data.items():
        setattr(t, k, v)
    db.commit()
    db.refresh(t)
    return t


def delete_topic(db: Session, topic_id: str) -> None:
    """Delete a topic."""
    t = db.query(Topic).filter(Topic.id == topic_id).first()
    if not t:
        raise HTTPException(404, f"Topic not found: {topic_id}")
    db.delete(t)
    db.commit()


def get_topic(db: Session, topic_id: str) -> Topic:
    """Get a single topic by ID."""
    t = db.query(Topic).filter(Topic.id == topic_id).first()
    if not t:
        raise HTTPException(404, f"Topic not found: {topic_id}")
    return t


def list_topics(db: Session, is_active: bool | None = None):
    """List topics with optional active filter."""
    q = db.query(Topic)
    if is_active is not None:
        q = q.filter(Topic.is_active == is_active)
    return q.order_by(Topic.updated_at.desc()).all()
