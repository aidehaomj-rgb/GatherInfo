"""Reports CRUD, generate, batch generate, export, download."""
import asyncio
import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.collection_schemas import (
    BatchGenerateRequest, BatchGenerateResult,
    ReportGenerateRequest, ReportListOut, ReportOut,
    WeeklyReportGenerateRequest, WeeklyReportGenerateResult,
)
from app.database import get_db
from app.models import Topic
from app.services.report_service import (
    list_reports as _list_reports,
    get_report as _get_report,
    delete_report as _delete_report,
    export_report_files as _export_report_files,
    download_report_file as _download_report_file,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["reports"])


@router.get("/reports", response_model=ReportListOut)
def list_reports(topic_id: str | None = None, days: int | None = Query(default=None, ge=1), db: Session = Depends(get_db)):
    reports, total = _list_reports(db, topic_id=topic_id, days=days)
    return ReportListOut(reports=reports, total=total)


@router.post("/reports/weekly-generate", response_model=WeeklyReportGenerateResult)
async def generate_weekly_reports(
    data: WeeklyReportGenerateRequest,
    db: Session = Depends(get_db),
):
    from app.weekly_report_engine import (
        WeeklySelectionPolicy, publish_weekly_digest,
    )

    try:
        reference = date.fromisoformat(data.week_start) if data.week_start else None
        policy = None
        if any(value is not None for value in (
            data.target_items, data.min_items, data.part_size,
        )):
            topic = db.query(Topic).filter(Topic.id == data.topic_id).first()
            if topic is None:
                raise ValueError(f"Topic not found: {data.topic_id}")
            policy = WeeklySelectionPolicy(
                target_items=data.target_items or topic.weekly_digest_target_items or 80,
                minimum_items=data.min_items or topic.weekly_digest_min_items or 60,
                maximum_part_items=data.part_size or topic.weekly_digest_part_size or 40,
            )
        publication = await publish_weekly_digest(
            db,
            data.topic_id,
            reference=reference,
            policy=policy,
            model_id=data.model_id,
            allow_partial=data.allow_partial,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("weekly report generation failed")
        raise HTTPException(500, "周刊生成失败，请查看服务端日志后重试") from exc

    plan = publication.plan
    return WeeklyReportGenerateResult(
        series_id=plan.series_id,
        period_key=plan.period_key,
        date_from=plan.window.start_utc.isoformat(),
        date_to=plan.window.end_utc.isoformat(),
        candidate_count=int(plan.selection_audit.get("eligible_count", 0)),
        selected_count=len(plan.ranked_ids),
        target_count=int(plan.selection_policy["target_items"]),
        documents=[ReportOut.model_validate(report) for report in publication.reports],
        selection_audit=dict(plan.selection_audit),
        warnings=list(publication.warnings),
        reused=publication.reused,
    )


@router.get("/reports/{report_id}", response_model=ReportOut)
def get_report(report_id: str, db: Session = Depends(get_db)):
    return _get_report(db, report_id)


@router.post("/reports/generate", response_model=ReportOut)
async def generate_report(data: ReportGenerateRequest, db: Session = Depends(get_db)):
    from app.report_engine import generate_report as gen
    try:
        report = await gen(
            topic_id=data.topic_id,
            model_id=data.model_id,
            report_type=data.report_type,
            title_override=data.title,
            collection_run_id=data.collection_run_id,
            collection_run_ids=data.collection_run_ids,
            date_from=data.date_from,
            date_to=data.date_to,
            model_name_override=data.model_name_override,
        )
        return report
    except ValueError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, f"Report generation failed: {e}")


@router.post("/reports/batch-generate", response_model=BatchGenerateResult)
async def batch_generate_reports(data: BatchGenerateRequest, db: Session = Depends(get_db)):
    from app.report_engine import generate_report as gen
    if not data.topic_ids:
        raise HTTPException(400, "topic_ids 不能为空")

    run_ids = data.collection_run_ids or []
    semaphore = asyncio.Semaphore(2)

    async def _one(idx: int, tid: str):
        run_id = run_ids[idx] if idx < len(run_ids) else None
        run_ids_for_topic = (
            (data.collection_run_ids_list or [None] * len(data.topic_ids))[idx]
            if data.collection_run_ids_list else None
        )
        async with semaphore:
            return await gen(
                topic_id=tid,
                model_id=data.model_id,
                report_type=data.report_type,
                collection_run_id=run_id,
                collection_run_ids=run_ids_for_topic,
                model_name_override=data.model_name_override,
            )

    tasks = [_one(i, tid) for i, tid in enumerate(data.topic_ids)]
    raw = await asyncio.gather(*tasks, return_exceptions=True)

    results: list[ReportOut] = []
    failed = 0
    for r in raw:
        if isinstance(r, Exception):
            failed += 1
            logger.error("batch report failed: %s", r)
            continue
        if getattr(r, "status", "") == "failed":
            failed += 1
        results.append(ReportOut.model_validate(r))
    return BatchGenerateResult(results=results, failed=failed)


@router.delete("/reports/{report_id}")
def delete_report(report_id: str, db: Session = Depends(get_db)):
    _delete_report(db, report_id)
    return {"ok": True}


@router.post("/reports/{report_id}/export", response_model=ReportOut)
def export_report_files(report_id: str, db: Session = Depends(get_db)):
    return _export_report_files(db, report_id)


@router.get("/reports/{report_id}/download")
def download_report(report_id: str, format: str = Query("pdf"), db: Session = Depends(get_db)):
    path, media_type, filename = _download_report_file(report_id, format, db)
    return FileResponse(path, media_type=media_type, filename=filename)
