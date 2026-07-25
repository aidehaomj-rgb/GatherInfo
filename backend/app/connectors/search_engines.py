"""
Baidu, Bing, 360, and general web search API connectors.

Configuration per source:
  auth_config: {
    "type": "baidu_custom" | "baidu_index" | "360_search" | "bing_search" | "google_custom",
    "api_key": "xxx",           # optional, falls back to env var
    "cx": "xxx",                # custom search engine ID (Google CSE)
    "region": "cn" | "us",      # search region
    "market": "zh-CN" | "en-US",
  }

Environment variables expected:
  BAIDU_API_KEY         → Baidu Custom Search API
  BAIDU_CX              → Baidu search engine ID
  GOOGLE_API_KEY        → Google Custom Search
  GOOGLE_CX             → Google CSE engine ID
  BING_API_KEY          → Bing Search API
  BAIDU_INDEX_API_KEY   → Baidu Index API (trend data)
"""
import logging
import os
import asyncio
from urllib.parse import urlencode

import httpx

from app.connectors.base import (
    BaseCollector, CollectResult, FetchItem,
    JobStatus, SourceConfig, register_collector,
)
from app.connectors._helpers import (
    result, detect_lang, infer_category, build_tags, extract_title, extract_body,
)

logger = logging.getLogger(__name__)


@register_collector("api_search")
class SearchEngineDispatcher(BaseCollector):
    """Dispatches to the appropriate search engine based on auth_config.type.

    Supports: tavily (default), baidu, bing, 360.
    The type is read from auth_config.get("search_type", "tavily").
    """
    channel = "api_search"

    def __init__(self, config: SourceConfig):
        super().__init__(config)
        ac = config.auth_config or {}
        self._search_type = ac.get("search_type", "tavily")
        self._delegate = self._build_delegate(ac, config)

    def _build_delegate(self, ac: dict, config: SourceConfig):
        st = self._search_type
        if st == "baidu":
            return BaiduDelegate(config, ac)
        elif st == "bing":
            return BingDelegate(config, ac)
        elif st == "360":
            return Search360Delegate(config, ac)
        else:
            from app.connectors.tavily_search import TavilyCollector
            return TavilyCollector(config)

    async def validate(self) -> bool:
        return await self._delegate.validate()

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        return await self._delegate.fetch(keywords, max_items)


class BaiduDelegate(BaseCollector):
    """Baidu Custom Search API."""
    channel = "api_search"
    BASE = "https://api.baidu.com/search/customsearch/v1"

    def __init__(self, config: SourceConfig, ac: dict):
        super().__init__(config)
        self.api_key = ac.get("api_key", "") or os.getenv("BAIDU_API_KEY", "")
        self.cx = ac.get("cx", "") or os.getenv("BAIDU_CX", "")
        self.region = ac.get("region", "cn")

    async def validate(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                resp = await c.get(self.BASE, params={
                    "access_token": self.api_key, "cx": self.cx,
                    "q": "test", "num": 1,
                })
                return resp.status_code == 200
        except Exception:
            return False

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        if not self.api_key:
            logger.warning("BAIDU_API_KEY not set for source %s", self.config.id)
            return self._error("BAIDU_API_KEY not set")
        if not self.cx:
            logger.warning("BAIDU_CX not set for source %s", self.config.id)
            return self._error("BAIDU_CX (search engine ID) not set")

        items: list[FetchItem] = []
        errors: list[str] = []
        per_query = min(10, max_items // max(1, len(keywords)))

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            for query in keywords:
                if len(items) >= max_items:
                    break
                try:
                    resp = await client.get(self.BASE, params={
                        "access_token": self.api_key,
                        "cx": self.cx, "q": query,
                        "num": per_query, "lr": "zh-CN",
                    })
                    if resp.status_code == 429:
                        errors.append(f"Rate limited: {query}")
                        logger.warning("Baidu rate limited for query: %s", query[:60])
                        await asyncio.sleep(2)
                        continue
                    resp.raise_for_status()
                    data = resp.json()
                    for r in data.get("items", data.get("results", [])):
                        title = r.get("title", "")
                        items.append(FetchItem(
                            title=title,
                            content=r.get("snippet", r.get("content", "")),
                            url=r.get("link", r.get("url", "")),
                            summary=r.get("snippet", "")[:500],
                            language="zh",
                            category=infer_category(title, r.get("snippet", "")),
                            suggested_tags=build_tags(title, r.get("snippet", "")),
                            raw_metadata={"engine": "baidu", "query": query, "region": self.region},
                        ))
                    await asyncio.sleep(1.0 / self.config.rate_limit_rps)
                except Exception as exc:
                    msg = f"Baidu search failed for '{query[:60]}': {exc}"
                    errors.append(msg)
                    logger.error("Baidu fetch error for source %s: %s", self.config.id, exc)

        logger.info("Baidu: %d items, %d errors for source %s", len(items), len(errors), self.config.id)
        return result(self._new_run_id(), self.config.id, items, errors)

    def _error(self, msg: str) -> CollectResult:
        return CollectResult(run_id=self._new_run_id(), source_id=self.config.id,
                             status=JobStatus.FAILED, items=[], error_log=[msg])


class BingDelegate(BaseCollector):
    """Microsoft Bing Web Search API."""
    channel = "api_search"
    BASE = "https://api.bing.microsoft.com/v7.0/search"

    def __init__(self, config: SourceConfig, ac: dict):
        super().__init__(config)
        self.api_key = ac.get("api_key", "") or os.getenv("BING_API_KEY", "")
        self.market = ac.get("market", "zh-CN")

    async def validate(self) -> bool:
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                resp = await c.get(self.BASE, params={"q": "test", "count": 1},
                                   headers={"Ocp-Apim-Subscription-Key": self.api_key})
                return resp.status_code == 200
        except Exception:
            return False

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        if not self.api_key:
            logger.warning("BING_API_KEY not set for source %s", self.config.id)
            return self._error("BING_API_KEY not set")

        items: list[FetchItem] = []
        errors: list[str] = []
        per_query = min(10, max_items // max(1, len(keywords)))

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            for query in keywords:
                if len(items) >= max_items:
                    break
                try:
                    resp = await client.get(self.BASE, params={
                        "q": query, "count": per_query, "mkt": self.market,
                    }, headers={"Ocp-Apim-Subscription-Key": self.api_key})
                    resp.raise_for_status()
                    data = resp.json()
                    for r in data.get("webPages", {}).get("value", []):
                        title = r.get("name", "")
                        items.append(FetchItem(
                            title=title,
                            content=r.get("snippet", ""),
                            url=r.get("url", ""),
                            summary=r.get("snippet", "")[:500],
                            language=detect_lang(f"{title} {r.get('snippet', '')}"),
                            category=infer_category(title, r.get("snippet", "")),
                            suggested_tags=build_tags(title, r.get("snippet", "")),
                            raw_metadata={"engine": "bing", "query": query, "market": self.market},
                        ))
                    await asyncio.sleep(1.0 / self.config.rate_limit_rps)
                except Exception as exc:
                    errors.append(f"Bing search failed for '{query[:60]}': {exc}")
                    logger.error("Bing fetch error for source %s: %s", self.config.id, exc)

        logger.info("Bing: %d items, %d errors for source %s", len(items), len(errors), self.config.id)
        return result(self._new_run_id(), self.config.id, items, errors)

    def _error(self, msg: str) -> CollectResult:
        return CollectResult(run_id=self._new_run_id(), source_id=self.config.id,
                             status=JobStatus.FAILED, items=[], error_log=[msg])


class Search360Delegate(BaseCollector):
    """360 Search API (unofficial, based on So.com)."""
    channel = "api_search"
    BASE = "https://www.so.com/s"

    async def validate(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10) as c:
                resp = await c.get(self.BASE, params={"q": "test"})
                return resp.status_code == 200
        except Exception:
            return False

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        items: list[FetchItem] = []
        errors: list[str] = []
        per_query = min(10, max_items // max(1, len(keywords)))

        async with httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
            headers={"User-Agent": "GatherInfo/0.4"},
            follow_redirects=True,
        ) as client:
            for query in keywords:
                if len(items) >= max_items:
                    break
                try:
                    resp = await client.get(self.BASE, params={"q": query, "pn": 0})
                    resp.raise_for_status()
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "lxml")
                    for el in soup.select(".result, .res-list, li.res")[:per_query]:
                        a = el.select_one("a[href]")
                        if not a:
                            continue
                        title = a.get_text(strip=True)
                        abs_el = el.select_one(".res-desc, .result-abs, .abstract")
                        snippet = abs_el.get_text(strip=True) if abs_el else ""
                        items.append(FetchItem(
                            title=title,
                            content=snippet,
                            url=a.get("href", ""),
                            summary=snippet[:500],
                            language="zh",
                            category=infer_category(title, snippet),
                            suggested_tags=build_tags(title, snippet),
                            raw_metadata={"engine": "360", "query": query},
                        ))
                    await asyncio.sleep(1.0 / self.config.rate_limit_rps)
                except Exception as exc:
                    errors.append(f"360 search failed for '{query[:60]}': {exc}")
                    logger.error("360 fetch error for source %s: %s", self.config.id, exc)

        logger.info("360: %d items, %d errors for source %s", len(items), len(errors), self.config.id)
        return result(self._new_run_id(), self.config.id, items, errors)

    def _error(self, msg: str) -> CollectResult:
        return CollectResult(run_id=self._new_run_id(), source_id=self.config.id,
                             status=JobStatus.FAILED, items=[], error_log=[msg])


# ── Targeted Web Scrape Collector for explicit URL lists ──

@register_collector("targeted_scrape")
class TargetedScrapeCollector(BaseCollector):
    """Targeted URL-based web scraping collector.

    Reads URLs from the `keywords` list (or source config's `target_urls` field).
    Each URL is fetched, parsed with BS4, and relevant content is extracted.
    """
    channel = "web_scrape"

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        if not keywords:
            return self._error("No target URLs specified (pass as keywords)")

        items: list[FetchItem] = []
        errors: list[str] = []
        ac = self.config.auth_config or {}
        content_sel = ac.get("content_selector",
                             "article, .content, main, .article-content, #content")

        async with httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
            headers={"User-Agent": "GatherInfo/0.4"},
            follow_redirects=True,
        ) as client:
            for url in keywords:
                if len(items) >= max_items:
                    break
                try:
                    resp = await client.get(url)
                    resp.raise_for_status()
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(resp.text, "lxml")
                    title = extract_title(soup)
                    body = extract_body(soup, content_sel)
                    items.append(FetchItem(
                        title=title or url,
                        content=body[:5000],
                        url=url,
                        summary=body[:500],
                        language=detect_lang(body),
                        suggested_tags=build_tags(title or "", body),
                        raw_metadata={"engine": "targeted_scrape"},
                    ))
                    await asyncio.sleep(
                        1.0 / self.config.rate_limit_rps if self.config.rate_limit_rps else 1.0)
                except Exception as exc:
                    errors.append(f"{url[:60]}: {exc}")
                    logger.error("Targeted scrape error for source %s url %s: %s",
                                 self.config.id, url[:80], exc)

        logger.info("TargetedScrape: %d items, %d errors for source %s",
                     len(items), len(errors), self.config.id)
        return result(self._new_run_id(), self.config.id, items, errors)

    def _error(self, msg: str) -> CollectResult:
        return CollectResult(run_id=self._new_run_id(), source_id=self.config.id,
                             status=JobStatus.FAILED, items=[], error_log=[msg])
