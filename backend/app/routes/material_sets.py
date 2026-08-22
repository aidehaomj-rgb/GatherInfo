"""Manage reusable information snapshots for downstream analysis."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.material_set_service import create_material_set, material_set_record
from app.models import CollectedItem, HandoffRun, MaterialSet, Report, Topic
from app.services.topic_item_query import filter_items_by_topic

router = APIRouter(prefix="/api/v1/material-sets", tags=["material-sets"])


class MaterialSetCreate(BaseModel):
    name: str | None = Field(default=None, max_length=300)
    topic_id: str | None = None
    report_id: str | None = None
    item_ids: list[str] | None = Field(default=None, max_length=500)
    collection_run_ids: list[str] | None = Field(default=None, max_length=100)


class HandoffRunOut(BaseModel):
    id: str
    material_set_id: str
    target: str
    status: str
    remote_session_id: str | None = None
    remote_batch_ids: list[str] = Field(default_factory=list)
    remote_task_ids: list[str] = Field(default_factory=list)
    request_summary: dict = Field(default_factory=dict)
    error_message: str | None = None
    created_at: datetime | None = None


class MaterialSetOut(BaseModel):
    id: str
    name: str
    topic_id: str | None = None
    report_id: str | None = None
    source_type: str
    source_ref_id: str | None = None
    item_ids: list[str]
    item_count: int
    is_archived: bool
    created_at: datetime | None = None
    handoff_runs: list[HandoffRunOut] = Field(default_factory=list)


@router.get("", response_model=list[MaterialSetOut])
def list_material_sets(
    topic_id: str | None = None,
    include_archived: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    query = db.query(MaterialSet)
    if topic_id:
        query = query.filter(MaterialSet.topic_id == topic_id)
    if not include_archived:
        query = query.filter(MaterialSet.is_archived == False)
    sets = query.order_by(MaterialSet.created_at.desc()).limit(limit).all()
    return [_with_runs(db, material_set) for material_set in sets]


@router.post("", response_model=MaterialSetOut)
def create_material_snapshot(
    data: MaterialSetCreate,
    db: Session = Depends(get_db),
):
    items, topic_id, source_type, source_ref_id = _resolve_create_scope(db, data)
    topic = db.query(Topic).filter(Topic.id == topic_id).first() if topic_id else None
    name = data.name or _default_name(topic, source_type)
    material_set = create_material_set(
        db,
        items,
        name=name,
        topic_id=topic_id,
        report_id=data.report_id,
        source_type=source_type,
        source_ref_id=source_ref_id,
    )
    return _with_runs(db, material_set)


@router.get("/{material_set_id}", response_model=MaterialSetOut)
def get_material_set(material_set_id: str, db: Session = Depends(get_db)):
    material_set = db.get(MaterialSet, material_set_id)
    if not material_set:
        raise HTTPException(404, "素材集不存在")
    return _with_runs(db, material_set)


@router.delete("/{material_set_id}")
def archive_material_set(material_set_id: str, db: Session = Depends(get_db)):
    material_set = db.get(MaterialSet, material_set_id)
    if not material_set:
        raise HTTPException(404, "素材集不存在")
    material_set.is_archived = True
    db.commit()
    return {"ok": True}


def _resolve_create_scope(
    db: Session,
    data: MaterialSetCreate,
) -> tuple[list[CollectedItem], str | None, str, str | None]:
    report = db.get(Report, data.report_id) if data.report_id else None
    if data.report_id and not report:
        raise HTTPException(404, "报告不存在")
    topic_id = data.topic_id or (report.topic_id if report else None)
    item_ids = list(data.item_ids or (report.item_ids if report else []) or [])
    query = db.query(CollectedItem)
    if item_ids:
        query = query.filter(CollectedItem.id.in_(item_ids))
        source_type = "report" if report else "selection"
        source_ref_id = report.id if report else None
    elif topic_id:
        query = filter_items_by_topic(query, topic_id)
        if data.collection_run_ids:
            query = query.filter(CollectedItem.run_id.in_(data.collection_run_ids))
            source_type = "batch"
            source_ref_id = data.collection_run_ids[0] if len(data.collection_run_ids) == 1 else None
        else:
            source_type = "topic"
            source_ref_id = topic_id
    else:
        raise HTTPException(400, "需提供主题、报告或条目")
    items = query.order_by(CollectedItem.published_at.desc()).limit(500).all()
    if not items:
        raise HTTPException(400, "所选范围内没有信息")
    return items, topic_id, source_type, source_ref_id


def _with_runs(db: Session, material_set: MaterialSet) -> dict:
    runs = (
        db.query(HandoffRun)
        .filter(HandoffRun.material_set_id == material_set.id)
        .order_by(HandoffRun.created_at.desc())
        .limit(20)
        .all()
    )
    return material_set_record(material_set, runs)


def _default_name(topic: Topic | None, source_type: str) -> str:
    prefix = topic.name if topic else "已选信息"
    label = {"report": "报告素材", "batch": "批次素材", "topic": "主题素材"}.get(
        source_type, "自选素材"
    )
    return f"{prefix} · {label}"
