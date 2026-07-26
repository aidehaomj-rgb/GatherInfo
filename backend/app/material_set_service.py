"""Persistence helpers for immutable evidence snapshots and delivery attempts."""
from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import CollectedItem, HandoffRun, MaterialSet

MAX_MATERIAL_SET_ITEMS = 500


def create_material_set(
    db: Session,
    items: list[CollectedItem | Any],
    *,
    name: str,
    topic_id: str | None = None,
    source_type: str = "selection",
    source_ref_id: str | None = None,
    report_id: str | None = None,
) -> MaterialSet:
    """Freeze membership and reuse an existing identical active snapshot."""
    item_ids = sorted({str(item.id) for item in items if getattr(item, "id", None)})
    if not item_ids:
        raise ValueError("素材集至少需要一条有效信息")
    if len(item_ids) > MAX_MATERIAL_SET_ITEMS:
        raise ValueError(f"素材集最多包含 {MAX_MATERIAL_SET_ITEMS} 条信息")
    fingerprint = _fingerprint(item_ids, topic_id, report_id)
    existing = (
        db.query(MaterialSet)
        .filter(
            MaterialSet.fingerprint == fingerprint,
            MaterialSet.is_archived == False,
        )
        .order_by(MaterialSet.created_at.desc())
        .first()
    )
    if existing:
        return existing
    material_set = MaterialSet(
        id=f"mat-{uuid4().hex[:16]}",
        name=name.strip()[:300] or "未命名素材集",
        topic_id=topic_id,
        report_id=report_id,
        source_type=source_type,
        source_ref_id=source_ref_id,
        item_ids=item_ids,
        item_count=len(item_ids),
        fingerprint=fingerprint,
    )
    db.add(material_set)
    db.commit()
    db.refresh(material_set)
    return material_set


def resolve_material_items(
    db: Session,
    material_set: MaterialSet,
) -> list[CollectedItem]:
    ids = list(material_set.item_ids or [])
    rows = db.query(CollectedItem).filter(CollectedItem.id.in_(ids)).all()
    by_id = {row.id: row for row in rows}
    return [by_id[item_id] for item_id in ids if item_id in by_id]


def record_handoff_run(
    db: Session,
    material_set: MaterialSet,
    target: str,
    status: str,
    *,
    remote_session_id: str | None = None,
    remote_batch_ids: list[str] | None = None,
    remote_task_ids: list[str] | None = None,
    request_summary: dict[str, Any] | None = None,
    error_message: str | None = None,
) -> HandoffRun:
    run = HandoffRun(
        id=f"handoff-{uuid4().hex[:16]}",
        material_set_id=material_set.id,
        target=target,
        status=status,
        remote_session_id=remote_session_id,
        remote_batch_ids=list(remote_batch_ids or []),
        remote_task_ids=list(remote_task_ids or []),
        request_summary=dict(request_summary or {}),
        error_message=error_message,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def material_set_record(
    material_set: MaterialSet,
    runs: list[HandoffRun] | None = None,
) -> dict[str, Any]:
    return {
        "id": material_set.id,
        "name": material_set.name,
        "topic_id": material_set.topic_id,
        "report_id": material_set.report_id,
        "source_type": material_set.source_type,
        "source_ref_id": material_set.source_ref_id,
        "item_ids": list(material_set.item_ids or []),
        "item_count": material_set.item_count,
        "is_archived": material_set.is_archived,
        "created_at": material_set.created_at,
        "handoff_runs": [handoff_run_record(run) for run in (runs or [])],
    }


def handoff_run_record(run: HandoffRun) -> dict[str, Any]:
    return {
        "id": run.id,
        "material_set_id": run.material_set_id,
        "target": run.target,
        "status": run.status,
        "remote_session_id": run.remote_session_id,
        "remote_batch_ids": list(run.remote_batch_ids or []),
        "remote_task_ids": list(run.remote_task_ids or []),
        "request_summary": dict(run.request_summary or {}),
        "error_message": run.error_message,
        "created_at": run.created_at,
    }


def _fingerprint(
    item_ids: list[str],
    topic_id: str | None,
    report_id: str | None,
) -> str:
    canonical = json.dumps(
        {"item_ids": item_ids, "topic_id": topic_id, "report_id": report_id},
        sort_keys=True,
        ensure_ascii=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
