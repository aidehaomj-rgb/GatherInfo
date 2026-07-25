"""Auto-generated route module."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db

logger = logging.getLogger(__name__)
from app.collection_schemas import (
    CollectResultOut, RunOut, ScheduleCreate, ScheduleOut,
)
from app.models import (
    CollectionRun, ScheduleConfig, SourceConfig, Topic,
)

router = APIRouter(prefix="/api/v1", tags=["schedules"])



@router.get("/schedules", response_model=list[ScheduleOut])
def list_schedules(db: Session = Depends(get_db)):
    return db.query(ScheduleConfig).all()


@router.post("/schedules", response_model=ScheduleOut, status_code=201)
async def create_schedule(data: ScheduleCreate, db: Session = Depends(get_db)):
    if db.query(ScheduleConfig).filter(ScheduleConfig.id == data.id).first():
        raise HTTPException(400, f"Schedule '{data.id}' exists")
    s = ScheduleConfig(**data.model_dump(exclude_none=True))
    db.add(s)
    db.commit()
    db.refresh(s)

    from app.scheduler import scheduler_instance
    if scheduler_instance:
        await scheduler_instance.add_schedule(s)
    return s


@router.delete("/schedules/{schedule_id}")
async def delete_schedule(schedule_id: str, db: Session = Depends(get_db)):
    s = db.query(ScheduleConfig).filter(ScheduleConfig.id == schedule_id).first()
    if not s:
        raise HTTPException(404)
    db.delete(s)
    db.commit()
    from app.scheduler import scheduler_instance
    if scheduler_instance:
        await scheduler_instance.remove_schedule(schedule_id)
    return {"ok": True}


@router.post("/schedules/{schedule_id}/run-now", response_model=list[CollectResultOut])
async def run_schedule_now(schedule_id: str, db: Session = Depends(get_db)):
    from app.engine import CollectionEngine

    engine = CollectionEngine(db)
    results = await engine.execute_schedule(schedule_id)
    out = []
    for r in results:
        run = db.query(CollectionRun).filter(CollectionRun.id == r.run_id).first()
        out.append(CollectResultOut(
            run=RunOut.model_validate(run) if run else RunOut(
                id=r.run_id, source_id=r.source_id, status=r.status or "unknown",
            ),
            total_items=len(r.items), items_new=r.items_new,
            errors=r.error_log,
        ))
    return out


