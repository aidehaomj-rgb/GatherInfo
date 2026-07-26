"""Push selected GatherInfo evidence into HaiSee translation-analysis tasks."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.handoff_service import (
    HAISEE_BASE_URL,
    HAISEE_WEB_URL,
    check_service_health,
    push_items_to_haisee,
)
from app.material_set_service import (
    create_material_set,
    record_handoff_run,
    resolve_material_items,
)
from app.models import CollectedItem, MaterialSet, Report, Topic

router = APIRouter(prefix="/api/v1/haisee", tags=["haisee"])


class HaiSeePushRequest(BaseModel):
    item_ids: list[str] | None = Field(default=None, max_length=500)
    report_id: str | None = None
    material_set_id: str | None = None


class HaiSeePushResponse(BaseModel):
    batch_id: str | None = None
    batch_ids: list[str] = Field(default_factory=list)
    task_ids: list[str]
    status: str
    web_url: str = HAISEE_WEB_URL
    material_set_id: str
    handoff_run_id: str


class HaiSeeHealthResponse(BaseModel):
    reachable: bool
    base_url: str
    message: str | None = None


@router.get("/health", response_model=HaiSeeHealthResponse)
async def haisee_health():
    return HaiSeeHealthResponse(
        **await check_service_health(HAISEE_BASE_URL, "/health")
    )


@router.post("/push", response_model=HaiSeePushResponse)
async def push_to_haisee(data: HaiSeePushRequest, db: Session = Depends(get_db)):
    item_ids = list(data.item_ids or [])
    if len(item_ids) != len(set(item_ids)):
        raise HTTPException(422, "条目 ID 不能重复")
    material_set = db.get(MaterialSet, data.material_set_id) if data.material_set_id else None
    if data.material_set_id and not material_set:
        raise HTTPException(404, "素材集不存在")
    report = db.get(Report, data.report_id) if data.report_id else None
    if data.report_id and not report:
        raise HTTPException(404, "报告不存在")
    if material_set:
        rows = resolve_material_items(db, material_set)
    else:
        if not item_ids and report:
            item_ids = list(report.item_ids or [])
        rows = _resolve_items(db, item_ids)
        topic_id = report.topic_id if report else (rows[0].topic_id if rows else None)
        topic = db.get(Topic, topic_id) if topic_id else None
        material_set = create_material_set(
            db,
            rows,
            name=f"{topic.name if topic else '已选信息'} · HaiSee 转译分析素材",
            topic_id=topic_id,
            source_type="report" if report else "selection",
            source_ref_id=report.id if report else None,
            report_id=report.id if report else None,
        )
    try:
        result = await push_items_to_haisee(rows)
        handoff = record_handoff_run(
            db,
            material_set,
            "haisee",
            result.get("status", "queued"),
            remote_batch_ids=result.get("batch_ids") or [],
            remote_task_ids=result.get("task_ids") or [],
            request_summary={"item_count": len(rows), "report_id": data.report_id},
        )
        return HaiSeePushResponse(
            **result,
            material_set_id=material_set.id,
            handoff_run_id=handoff.id,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        record_handoff_run(
            db,
            material_set,
            "haisee",
            "failed",
            request_summary={"item_count": len(rows), "report_id": data.report_id},
            error_message=str(exc),
        )
        raise HTTPException(502, f"推送 HaiSee 失败：{exc}") from exc


def _resolve_items(db: Session, item_ids: list[str]) -> list[CollectedItem]:
    if not item_ids:
        raise HTTPException(400, "需提供条目、归档报告或素材集")
    rows = db.query(CollectedItem).filter(CollectedItem.id.in_(item_ids)).all()
    by_id = {row.id: row for row in rows}
    missing = [item_id for item_id in item_ids if item_id not in by_id]
    if missing:
        raise HTTPException(404, f"有 {len(missing)} 条信息不存在")
    return [by_id[item_id] for item_id in item_ids]
