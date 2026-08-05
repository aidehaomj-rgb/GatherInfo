"""
Source health checker — batch-check all active sources and mark health status.

Health status values:
  healthy     — URL reachable, returns valid content (RSS=XML, web=HTML)
  degraded    — URL reachable but returns unexpected content type (e.g. RSS returns HTML)
  failed      — URL reachable but server error (5xx)
  unreachable — URL not reachable (connection error, timeout, DNS failure)
  unknown     — Not yet checked
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

import httpx
from sqlalchemy.orm import Session

from app.models import SourceConfig


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


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


async def check_source_health(
    db: Session,
    source_id: Optional[str] = None,
    batch_size: int = 20,
    timeout: float = 15.0,
) -> dict:
    """
    Check health of all active sources (or a single source if source_id given).

    Returns a summary dict with counts by status.
    """
    query = db.query(SourceConfig).filter(SourceConfig.is_active == True)
    if source_id:
        query = query.filter(SourceConfig.id == source_id)

    sources = query.all()
    if not sources:
        return {"total": 0, "healthy": 0, "degraded": 0, "failed": 0, "unreachable": 0}

    now = _utc_now()
    summary = {"total": len(sources), "healthy": 0, "degraded": 0, "failed": 0, "unreachable": 0}

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

    db.commit()
    return summary


def check_source_health_sync(
    db: Session,
    source_id: Optional[str] = None,
) -> dict:
    """Synchronous wrapper for check_source_health."""
    return asyncio.run(check_source_health(db, source_id))