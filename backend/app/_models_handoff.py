"""Reusable evidence snapshots and downstream handoff history."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, Text

from app.database import Base


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class MaterialSet(Base):
    """Immutable membership snapshot that can be sent downstream repeatedly."""

    __tablename__ = "material_sets"

    id = Column(String(80), primary_key=True)
    name = Column(String(300), nullable=False)
    topic_id = Column(String(80), ForeignKey("topics.id"), nullable=True)
    report_id = Column(String(80), ForeignKey("reports.id"), nullable=True)
    source_type = Column(String(30), nullable=False, default="selection")
    source_ref_id = Column(String(80), nullable=True)
    item_ids = Column(JSON, nullable=False)
    item_count = Column(Integer, nullable=False, default=0)
    fingerprint = Column(String(64), nullable=False, index=True)
    is_archived = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now)


class HandoffRun(Base):
    """One delivery attempt for a reusable material set."""

    __tablename__ = "handoff_runs"

    id = Column(String(80), primary_key=True)
    material_set_id = Column(
        String(80), ForeignKey("material_sets.id"), nullable=False, index=True
    )
    target = Column(String(30), nullable=False)
    status = Column(String(30), nullable=False, default="pending")
    remote_session_id = Column(String(160), nullable=True)
    remote_batch_ids = Column(JSON, nullable=True)
    remote_task_ids = Column(JSON, nullable=True)
    request_summary = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now)
