"""
Source health checker — batch-check all active sources and mark health status.

Health status values:
  healthy     — URL reachable, returns valid content (RSS=XML, web=HTML)
  degraded    — URL reachable but returns unexpected content type (e.g. RSS returns HTML)
  failed      — URL reachable but server error (5xx)
  unreachable — URL not reachable (connection error, timeout, DNS failure)
  unknown     — Not yet checked

On a full batch check (source_id=None), completely unreachable sources that carry
no value (no collected items, no collection runs, not referenced by any topic or
schedule) are deleted — after backing up the DB — and a history event is written
to the notification system.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

import httpx
from sqlalchemy.orm import Session

from app.models import (
    CollectedItem,
    CollectionRun,
    ScheduleConfig,
    SourceConfig,
    Topic,
)
from app.notification_models import NotificationBatch

logger = logging.getLogger(__name__)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _channel_name(source: SourceConfig) -> str:
    return source.channel.value if hasattr(source.channel, "value") else str(source.channel)


async def _check_single_source(
    source: SourceConfig,
    client: httpx.AsyncClient,
) -> tuple[str, str]:
    """Check a single source URL and return (health_status, detail)."""
    url = source.base_url or source.homepage_url or ""
    if not url:
        return "unreachable", "No URL configured"

    try:
        resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
    except httpx.ConnectError as e:
        return "unreachable", f"Connection error: {e}"[:200]
    except httpx.TimeoutException:
        return "unreachable", "Request timed out"
    except Exception as e:
        return "unreachable", f"{type(e).__name__}: {e}"[:200]

    status = resp.status_code
    content_type = resp.headers.get("content-type", "")
    body = resp.text.strip() if resp.text else ""

    if status >= 500:
        return "failed", f"HTTP {status} server error"
    if status >= 400:
        return "failed", f"HTTP {status} client error"
    if status != 200:
        return "degraded", f"HTTP {status} redirect"

    # Check content type for RSS sources
    if source.channel and source.channel.value == "rss":
        is_xml = (
            "xml" in content_type.lower()
            or body.startswith("<?xml")
            or body.startswith("<feed")
            or body.startswith("<rss")
        )
        if not is_xml:
            return "degraded", f"Expected RSS/XML but got {content_type or 'unknown'}"

    return "healthy", f"HTTP {status}, {content_type[:60]}"


def _backup_db() -> None:
    """Back up the SQLite DB file before destructive deletion."""
    from app.database import DATABASE_URL

    if not DATABASE_URL.startswith("sqlite"):
        return
    path = os.path.abspath(DATABASE_URL.replace("sqlite:///", "", 1))
    if not os.path.exists(path):
        return
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    try:
        shutil.copy(path, f"{path}.bak-{stamp}")
        logger.info("DB backed up to %s.bak-%s before source deletion", path, stamp)
    except Exception as exc:  # pragma: no cover - defensive
        logger.warning("DB backup failed: %s", exc)


def _referenced_source_ids(db: Session) -> set[str]:
    """Collect source ids referenced by topics or schedules (must be preserved)."""
    referenced: set[str] = set()
    for (source_ids,) in db.query(Topic.source_ids).all():
        if isinstance(source_ids, (list, tuple, set)):
            referenced.update(str(s) for s in source_ids if s)
    for (source_ids,) in db.query(ScheduleConfig.source_ids).all():
        if isinstance(source_ids, (list, tuple, set)):
            referenced.update(str(s) for s in source_ids if s)
    return referenced


def _delete_worthless_unreachable(
    db: Session,
    unreachable_sources: list[SourceConfig],
) -> list[dict]:
    """Delete unreachable sources that carry no value.

    A source is considered worthless when it is unreachable AND has:
      - no collected items
      - no collection runs
      - no reference from any topic or schedule
    """
    if not unreachable_sources:
        return []

    referenced = _referenced_source_ids(db)
    to_delete: list[SourceConfig] = []
    deleted: list[dict] = []

    for src in unreachable_sources:
        if src.id in referenced:
            continue
        has_items = (
            db.query(CollectedItem.id).filter(CollectedItem.source_id == src.id).first()
            is not None
        )
        if has_items:
            continue
        has_runs = (
            db.query(CollectionRun.id).filter(CollectionRun.source_id == src.id).first()
            is not None
        )
        if has_runs:
            continue
        to_delete.append(src)
        deleted.append({
            "id": src.id,
            "name": src.name,
            "reason": (src.health_detail or "不可达")[:200],
        })

    if not to_delete:
        return []

    _backup_db()
    for src in to_delete:
        db.delete(src)
    db.commit()
    logger.info("Deleted %d worthless unreachable sources", len(to_delete))
    return deleted


def _record_health_check_batch(db: Session, report: dict) -> None:
    """Persist a health-check history event into the notification system."""
    status = "failed" if report["unreachable"] > 0 else (
        "partial" if report["failed"] > 0 or report["degraded"] > 0 else "completed"
    )
    try:
        rec = NotificationBatch(
            id=f"nb-{uuid4().hex[:12]}",
            topic_id=None,
            topic_name="信息源健康检查",
            batch_id=None,
            total_new=0,
            source_count=report["total"],
            details=json.dumps(
                {
                    "event": "source_health_check",
                    "summary": {
                        k: report[k]
                        for k in ("total", "healthy", "degraded", "failed", "unreachable")
                    },
                    "sources": report["sources"],
                    "deleted": report["deleted"],
                },
                ensure_ascii=False,
            ),
            status=status,
        )
        db.add(rec)
        db.commit()
    except Exception as exc:  # pragma: no cover - non-blocking
        logger.warning("Failed to record health-check history: %s", exc)


async def check_source_health(
    db: Session,
    source_id: Optional[str] = None,
    batch_size: int = 20,
    timeout: float = 15.0,
) -> dict:
    """
    Check health of all active sources (or a single source if source_id given).

    Returns a detailed report with summary counts, per-source details for
    non-healthy sources, and the list of deleted worthless sources.
    """
    query = db.query(SourceConfig).filter(SourceConfig.is_active == True)
    if source_id:
        query = query.filter(SourceConfig.id == source_id)

    sources = query.all()
    empty_report = {
        "total": 0, "healthy": 0, "degraded": 0, "failed": 0,
        "unreachable": 0, "sources": [], "deleted": [],
    }
    if not sources:
        return empty_report

    now = _utc_now()
    summary = {"total": len(sources), "healthy": 0, "degraded": 0, "failed": 0, "unreachable": 0}
    detail_list: list[dict] = []
    unreachable_sources: list[SourceConfig] = []

    # Process in batches to avoid overwhelming the network
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=True,
        verify=False,
    ) as client:
        for i in range(0, len(sources), batch_size):
            batch = sources[i : i + batch_size]
            tasks = [_check_single_source(src, client) for src in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for src, result in zip(batch, results):
                if isinstance(result, Exception):
                    status, detail = "unreachable", f"Exception: {result}"[:200]
                else:
                    status, detail = result

                src.health_status = status
                src.health_checked_at = now
                src.health_detail = detail
                summary[status] = summary.get(status, 0) + 1

                if status != "healthy":
                    detail_list.append({
                        "id": src.id,
                        "name": src.name,
                        "channel": _channel_name(src),
                        "url": (src.base_url or src.homepage_url or "")[:400],
                        "status": status,
                        "detail": detail,
                    })
                if status == "unreachable":
                    unreachable_sources.append(src)

    db.commit()

    # Only auto-delete + record history on a full batch check.
    deleted: list[dict] = []
    if source_id is None:
        deleted = _delete_worthless_unreachable(db, unreachable_sources)

    report = {**summary, "sources": detail_list, "deleted": deleted}
    if source_id is None:
        _record_health_check_batch(db, report)
    return report


def check_source_health_sync(
    db: Session,
    source_id: Optional[str] = None,
) -> dict:
    """Synchronous wrapper for check_source_health."""
    return asyncio.run(check_source_health(db, source_id))
