"""Backfill publication dates from publicly accessible original pages."""
from __future__ import annotations

import asyncio
from datetime import datetime

import httpx

from app.database import SessionLocal
from app.models import CollectedItem
from app.web_content_extractor import extract_article_text


async def backfill_published_dates(
    limit: int = 1000, concurrency: int = 12, timeout_seconds: int = 6,
) -> dict[str, int]:
    db = SessionLocal()
    try:
        items = (
            db.query(CollectedItem)
            .filter(CollectedItem.published_at.is_(None), CollectedItem.url.isnot(None))
            .order_by(CollectedItem.collected_at.desc())
            .limit(limit)
            .all()
        )
        semaphore = asyncio.Semaphore(concurrency)

        async with httpx.AsyncClient(follow_redirects=True, timeout=timeout_seconds) as client:
            async def resolve(item: CollectedItem) -> datetime | None:
                async with semaphore:
                    try:
                        response = await client.get(
                            item.url,
                            headers={"User-Agent": "GatherInfo/0.5 (date backfill)"},
                        )
                        response.raise_for_status()
                        value = extract_article_text(response.text, item.url).get("published_at")
                        return datetime.fromisoformat(str(value).replace("Z", "+00:00")) if value else None
                    except Exception:
                        return None

            dates = await asyncio.gather(*(resolve(item) for item in items))

        updated = 0
        for item, published_at in zip(items, dates):
            if published_at:
                item.published_at = published_at
                updated += 1
        db.commit()
        return {"checked": len(items), "updated": updated, "unresolved": len(items) - updated}
    finally:
        db.close()
