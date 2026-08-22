"""Topics CRUD, Categories CRUD, Collection execution."""
import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.collection_schemas import (
    CategoryCreate, CategoryOut, CategoryUpdate,
    CollectRequest, CollectResultOut, CollectionBatchSummaryOut,
    RunOut, TopicCreate, TopicOut, TopicUpdate,
)
from app.database import get_db
from app.engine import CollectionEngine
from app.models import Category, CollectionBatch, CollectionRun, Topic

from ._helpers import _gen_id, _normalize_topic_payload, _topic_out

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["topics"])


# ── Topics ──────────────────────────────────────────────────────────────

@router.get("/topics", response_model=list[TopicOut])
def list_topics(is_active: bool | None = None, db: Session = Depends(get_db)):
    q = db.query(Topic)
    if is_active is not None:
        q = q.filter(Topic.is_active == is_active)
    return [_topic_out(db, t) for t in q.all()]


@router.post("/topics", response_model=TopicOut, status_code=201)
def create_topic(data: TopicCreate, db: Session = Depends(get_db)):
    payload = _normalize_topic_payload(data.model_dump())
    topic_id = payload.get("id")
    if not topic_id:
        topic_id = _gen_id(
            data.name,
            exists_fn=lambda c: db.query(Topic).filter(Topic.id == c).first() is not None,
        )
    elif db.query(Topic).filter(Topic.id == topic_id).first():
        raise HTTPException(400, f"主题 '{topic_id}' 已存在")
    payload["id"] = topic_id
    try:
        t = Topic(**payload)
        db.add(t)
        db.commit()
        db.refresh(t)
    except Exception as exc:
        db.rollback()
        logger.error("create_topic failed: %s", exc)
        raise HTTPException(500, f"创建主题失败: {exc}")
    return _topic_out(db, t)


@router.get("/topics/{topic_id}", response_model=TopicOut)
def get_topic(topic_id: str, db: Session = Depends(get_db)):
    t = db.query(Topic).filter(Topic.id == topic_id).first()
    if not t:
        raise HTTPException(404)
    return _topic_out(db, t)


@router.put("/topics/{topic_id}", response_model=TopicOut)
async def update_topic(topic_id: str, data: TopicUpdate, db: Session = Depends(get_db)):
    t = db.query(Topic).filter(Topic.id == topic_id).first()
    if not t:
        raise HTTPException(404)
    payload = _normalize_topic_payload(data.model_dump(exclude_unset=True))
    target = int(payload.get("weekly_digest_target_items", t.weekly_digest_target_items or 80))
    part_size = int(payload.get("weekly_digest_part_size", t.weekly_digest_part_size or 40))
    minimum = int(payload.get("weekly_digest_min_items", t.weekly_digest_min_items or 60))
    if target > part_size * 2 or minimum > target:
        raise HTTPException(
            400,
            "周刊配置必须满足：两卷容量覆盖目标条数，且发布下限不超过目标条数",
        )
    try:
        for k, v in payload.items():
            setattr(t, k, v)
        db.commit()
        db.refresh(t)
        # Keep the in-memory APScheduler jobs in sync with topic edits.  This
        # is especially important when a user disables periodic collection
        # from the topic management page.
        from app.scheduler import scheduler_instance
        if scheduler_instance:
            await scheduler_instance.reload()
    except Exception as exc:
        db.rollback()
        logger.error("update_topic failed: %s", exc)
        raise HTTPException(500, f"更新主题失败: {exc}")
    return _topic_out(db, t)


@router.delete("/topics/{topic_id}")
def delete_topic(topic_id: str, db: Session = Depends(get_db)):
    t = db.query(Topic).filter(Topic.id == topic_id).first()
    if not t:
        raise HTTPException(404)
    db.delete(t)
    db.commit()
    return {"ok": True}


# ── Categories ──────────────────────────────────────────────────────────

@router.get("/categories", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.created_at).all()


@router.post("/categories", response_model=CategoryOut, status_code=201)
def create_category(data: CategoryCreate, db: Session = Depends(get_db)):
    if db.query(Category).filter(Category.id == data.id).first():
        raise HTTPException(400, f"Category '{data.id}' exists")
    cat = Category(**data.model_dump())
    db.add(cat)
    db.commit()
    db.refresh(cat)
    return cat


@router.put("/categories/{category_id}", response_model=CategoryOut)
def update_category(category_id: str, data: CategoryUpdate, db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(404)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(cat, k, v)
    db.commit()
    db.refresh(cat)
    return cat


@router.delete("/categories/{category_id}")
def delete_category(category_id: str, db: Session = Depends(get_db)):
    cat = db.query(Category).filter(Category.id == category_id).first()
    if not cat:
        raise HTTPException(404)
    db.query(Topic).filter(Topic.category_id == category_id).update({"category_id": None})
    db.delete(cat)
    db.commit()
    return {"ok": True}


# ── Collection ──────────────────────────────────────────────────────────

@router.post("/collect", response_model=list[CollectResultOut])
async def run_collection(data: CollectRequest, db: Session = Depends(get_db)):
    engine = CollectionEngine(db)

    if data.topic_id:
        try:
            results = await engine.collect_topic(
                data.topic_id,
                research_prompt=data.research_prompt,
                research_model_id=data.research_model_id,
                only_source_ids=data.source_ids,
            )
        except ValueError as e:
            raise HTTPException(400, str(e))
        try:
            topic = db.query(Topic).filter(Topic.id == data.topic_id).first()
            total_new = sum(result.items_new for result in results)
            if topic and topic.auto_report and total_new > 0:
                from app.report_engine import generate_report as auto_gen
                logger.info("Auto-report triggered for topic %s after manual collection", data.topic_id)
                run_ids = [result.run_id for result in results if getattr(result, "run_id", None)]
                asyncio.ensure_future(auto_gen(
                    topic_id=data.topic_id,
                    model_id=topic.auto_report_model_id,
                    report_type=topic.auto_report_type or "analytical",
                    collection_run_ids=run_ids,
                ))
        except Exception as exc:
            logger.warning("Auto-report trigger failed for %s: %s", data.topic_id, exc)
    elif data.source_id:
        keywords = data.keywords or []
        r = await engine.collect_from_source(data.source_id, keywords)
        results = [r]
    else:
        raise HTTPException(400, "Specify topic_id or source_id")

    return _build_collect_results(results, db)


def _build_collect_results(results, db: Session) -> list[CollectResultOut]:
    out = []
    for r in results:
        run = db.query(CollectionRun).filter(CollectionRun.id == r.run_id).first()
        batch = (
            db.query(CollectionBatch).filter(CollectionBatch.id == run.batch_id).first()
            if run and run.batch_id else None
        )
        summary = CollectionBatchSummaryOut(
            batch_id=batch.id, topic_id=batch.topic_id, status=batch.status or "pending",
            current_round=batch.current_round or 0, max_rounds=batch.max_rounds or 2,
            target=batch.target, metrics=batch.metrics, acceptance=batch.acceptance,
            gaps=batch.gaps or [], source_plan=batch.source_plan,
            round_summaries=batch.round_summaries or [], stop_reason=batch.stop_reason,
            created_at=batch.created_at, started_at=batch.started_at,
            completed_at=batch.completed_at, updated_at=batch.updated_at,
        ) if batch else None
        out.append(CollectResultOut(
            run=RunOut.model_validate(run) if run else RunOut(
                id=r.run_id, source_id=r.source_id, status=r.status or "unknown",
                items_found=len(r.items), items_new=r.items_new, items_failed=r.items_failed,
                error_log=r.error_log,
            ),
            total_items=len(r.items), items_new=r.items_new,
            errors=r.error_log,
            batch_summary=summary,
        ))
    return out
