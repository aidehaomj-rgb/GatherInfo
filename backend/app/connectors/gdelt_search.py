"""GDELT DOC API search fallback for global enforcement news discovery."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import logging
import time

import httpx

from app.connectors.base import BaseCollector, CollectResult, FetchItem
from app.connectors._helpers import detect_lang, infer_category, result
from app.connectors.tavily_search import _parse_search_query


logger = logging.getLogger(__name__)


class GDELTSearchCollector(BaseCollector):
    """Search global news without an API key, respecting GDELT's 5-second limit."""

    channel = "gdelt_search"
    BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"

    async def fetch(
        self,
        keywords: list[str],
        max_items: int = 100,
    ) -> CollectResult:
        queries = keywords or self.config.default_keywords or ["customs seizure smuggling"]
        # GDELT permits one request every five seconds. Cover alternating
        # geographic missions each run so a weekly pair covers the full matrix
        # without holding one collection open for more than five minutes.
        if len(queries) > 18:
            rotation = datetime.now(timezone.utc).isocalendar().week % 2
            queries = queries[rotation::2]
        per_query = max(1, min(10, max_items // max(1, len(queries))))
        items: list[FetchItem] = []
        errors: list[str] = []

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            for index, query in enumerate(queries):
                if len(items) >= max_items:
                    break
                query_text, directives = _parse_search_query(query)
                jurisdiction = directives.get("jurisdiction") or "Global"
                gdelt_query = (
                    f'"{jurisdiction}" customs '
                    "(seizure OR seized OR smuggling OR arrested OR confiscated)"
                    if jurisdiction != "Global"
                    else "customs (seizure OR seized OR smuggling OR arrested OR confiscated)"
                )
                params = {
                    "query": gdelt_query,
                    "mode": "artlist",
                    "format": "json",
                    "maxrecords": per_query,
                    "sort": "datedesc",
                }
                if self.window_start:
                    params["startdatetime"] = _gdelt_datetime(self.window_start)
                if self.window_end:
                    params["enddatetime"] = _gdelt_datetime(self.window_end)

                request_started = time.monotonic()
                response = await self._request(client, params)
                if response is None:
                    errors.append(f"GDELT rate limited or unavailable: {jurisdiction}")
                else:
                    for article in response.get("articles", []):
                        if not isinstance(article, dict):
                            continue
                        title = str(article.get("title") or "").strip()
                        url = str(article.get("url") or "").strip()
                        if not title or not url:
                            continue
                        seen_at = _parse_gdelt_date(article.get("seendate"))
                        items.append(FetchItem(
                            title=title,
                            content=title,
                            summary=title,
                            url=url,
                            published_at=seen_at,
                            language=detect_lang(
                                f"{article.get('language') or ''} {title}"
                            ),
                            category=infer_category(title, title),
                            quality_score=0.55,
                            relevance_score=0.6,
                            raw_metadata={
                                "engine": "gdelt",
                                "query": query_text,
                                "search_jurisdiction": jurisdiction,
                                "search_country": directives.get("country"),
                                "source_domain": article.get("domain"),
                                "source_country": article.get("sourcecountry"),
                                "gdelt_seen_at": seen_at,
                                "date_verification": "search_index_only",
                                "allow_undated_results": False,
                                "allow_unfiltered_results": True,
                            },
                        ))
                if index < len(queries) - 1:
                    elapsed = time.monotonic() - request_started
                    await asyncio.sleep(max(0.0, 5.2 - elapsed))

        return result(self._new_run_id(), self.config.id, items[:max_items], errors)

    async def _request(
        self,
        client: httpx.AsyncClient,
        params: dict,
    ) -> dict | None:
        for attempt in range(2):
            try:
                response = await client.get(self.BASE_URL, params=params)
                if response.status_code == 429:
                    if attempt == 0:
                        await asyncio.sleep(5.5)
                        continue
                    return None
                response.raise_for_status()
                payload = response.json()
                return payload if isinstance(payload, dict) else None
            except Exception as exc:
                logger.warning("GDELT search request failed: %s", exc)
                return None
        return None


def _gdelt_datetime(value: datetime) -> str:
    aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return aware.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")


def _parse_gdelt_date(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y%m%dT%H%M%SZ").replace(
            tzinfo=timezone.utc
        ).isoformat()
    except ValueError:
        return None
