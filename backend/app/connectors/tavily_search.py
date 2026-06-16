"""
Tavily Search connector for GatherInfo.
"""
import logging
import os
import asyncio

import httpx

from app.connectors.base import (
    BaseCollector, CollectResult, FetchItem,
    JobStatus, SourceConfig, register_collector,
)
from app.connectors._helpers import detect_lang, infer_category, build_tags, result

logger = logging.getLogger(__name__)


@register_collector("api_search")
class TavilyCollector(BaseCollector):
    channel = "api_search"
    BASE_URL = "https://api.tavily.com/search"

    def __init__(self, config: SourceConfig):
        super().__init__(config)
        self.auth_config = config.auth_config or {}
        self.search_type = self.auth_config.get("search_type") or "tavily"
        self.api_key = (
            config.api_key
            or os.getenv(config.api_key_ref or "")
            or os.getenv("TAVILY_API_KEY", "")
        )
        if self.search_type in ("baidu", "baidu_qianfan"):
            self.api_key = (
                config.api_key
                or os.getenv(config.api_key_ref or "")
                or os.getenv("BAIDU_QIANFAN_API_KEY", "")
                or os.getenv("BAIDU_API_KEY", "")
            )

    async def validate(self) -> bool:
        if self.search_type in ("baidu", "baidu_qianfan"):
            return bool(self.api_key)
        if not self.api_key:
            return False
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(self.BASE_URL, json={
                    "api_key": self.api_key, "query": "test", "max_results": 1,
                })
                return resp.status_code == 200
        except Exception:
            return False

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        if self.search_type in ("baidu", "baidu_qianfan"):
            return await self._fetch_baidu_qianfan(keywords, max_items)

        if not self.api_key:
            logger.warning("TAVILY_API_KEY not set for source %s", self.config.id)
            return CollectResult(
                run_id=self._new_run_id(), source_id=self.config.id,
                status=JobStatus.FAILED, items=[],
                error_log=["TAVILY_API_KEY not set"],
            )

        queries = (
            self.config.default_keywords
            if self.auth_config.get("prefer_default_keywords")
            else None
        ) or keywords or self.config.default_keywords or ["global trade news"]
        items: list[FetchItem] = []
        errors: list[str] = []
        per_query = max(1, min(20, max_items // max(1, len(queries))))

        include_domains = _build_domain_filter(self.config.default_categories)
        include_domains_param = include_domains if include_domains else None

        async with httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
            limits=httpx.Limits(max_connections=3),
        ) as client:
            for query in queries:
                if len(items) >= max_items:
                    break
                try:
                    payload = {
                        "api_key": self.api_key,
                        "query": query,
                        "search_depth": "advanced",
                        "max_results": per_query,
                        "include_answer": False,
                        "include_raw_content": False,
                    }
                    if include_domains_param:
                        payload["include_domains"] = include_domains_param
                    resp = await client.post(self.BASE_URL, json=payload)
                    if resp.status_code == 429:
                        errors.append(f"Rate limited: {query}")
                        logger.warning("Tavily rate limited for query: %s", query[:60])
                        continue
                    resp.raise_for_status()
                    data = resp.json()

                    for r in data.get("results", []):
                        title = r.get("title", "")
                        content = r.get("content", "")
                        url = r.get("url", "")

                        pub_date = r.get("published_date", None)
                        if pub_date and isinstance(pub_date, str):
                            try:
                                from datetime import timezone, datetime
                                dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                                pub_date = dt.isoformat()
                            except (ValueError, TypeError):
                                pub_date = None

                        items.append(FetchItem(
                            title=title,
                            content=content,
                            url=url,
                            published_at=pub_date,
                            summary=content[:500] if content else None,
                            language=detect_lang(f"{url} {content}"),
                            category=infer_category(title, content),
                            suggested_tags=build_tags(title, content),
                            quality_score=r.get("score", 0.5),
                            relevance_score=r.get("score", 0.5),
                            raw_metadata={"engine": "tavily", "query": query,
                                          "score": r.get("score")},
                        ))

                    await asyncio.sleep(
                        1.0 / self.config.rate_limit_rps if self.config.rate_limit_rps else 1.0)

                except Exception as exc:
                    msg = f"Query '{query[:40]}': {exc}"
                    errors.append(msg)
                    logger.error("Tavily fetch error for source %s: %s", self.config.id, exc)

        logger.info("Tavily: %d items, %d errors for source %s",
                     len(items), len(errors), self.config.id)
        return result(self._new_run_id(), self.config.id, items, errors)

    async def _fetch_baidu_qianfan(
        self, keywords: list[str], max_items: int = 100
    ) -> CollectResult:
        if not self.api_key:
            logger.warning("BAIDU_QIANFAN_API_KEY not set for source %s", self.config.id)
            return CollectResult(
                run_id=self._new_run_id(), source_id=self.config.id,
                status=JobStatus.FAILED, items=[],
                error_log=[
                    "BAIDU_QIANFAN_API_KEY not set. 百度千帆搜索有免费额度，但仍需配置 API Key。"
                ],
            )

        endpoint = (
            self.config.api_endpoint
            or self.auth_config.get("api_endpoint")
            or "/v2/ai_search/web_search"
        )
        base = (self.config.base_url or "https://qianfan.baidubce.com").rstrip("/")
        url = endpoint if endpoint.startswith("http") else base + "/" + endpoint.lstrip("/")
        queries = (
            self.config.default_keywords
            if self.auth_config.get("prefer_default_keywords")
            else None
        ) or keywords or self.config.default_keywords or ["进出口"]

        items: list[FetchItem] = []
        errors: list[str] = []
        per_query = max(1, min(10, max_items // max(1, len(queries))))

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "GatherInfo/0.4 (Baidu Qianfan Search)",
        }

        async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
            for query in queries:
                if len(items) >= max_items:
                    break
                try:
                    body = {
                        "query": query,
                        "search_source": self.auth_config.get("search_source", "baidu_search_v2"),
                        "resource_type_filter": self.auth_config.get("resource_type_filter", []),
                    }
                    resp = await client.post(url, headers=headers, json=body)
                    if resp.status_code == 401:
                        errors.append(f"百度搜索认证失败，请检查 BAIDU_QIANFAN_API_KEY: {query}")
                        continue
                    if resp.status_code == 429:
                        errors.append(f"百度搜索触发限流: {query}")
                        continue
                    resp.raise_for_status()
                    data = resp.json()

                    for rec in _extract_baidu_records(data)[:per_query]:
                        title = _first_text(rec, ["title", "name", "doc_title"]) or query
                        content = _first_text(
                            rec, ["content", "summary", "snippet", "abstract", "description"]
                        )
                        url_value = _first_text(rec, ["url", "link", "href", "source_url"])
                        published_at = _first_text(
                            rec, ["published_at", "publish_time", "date", "time"]
                        )
                        text = f"{title} {content}"
                        items.append(FetchItem(
                            title=title,
                            content=content or None,
                            url=url_value or None,
                            published_at=published_at or None,
                            summary=(content or "")[:500] or None,
                            language=detect_lang(text),
                            category=infer_category(title, content),
                            suggested_tags=build_tags(title, content),
                            quality_score=0.7,
                            relevance_score=0.7,
                            raw_metadata={"engine": "baidu_qianfan", "query": query},
                        ))

                    await asyncio.sleep(
                        1.0 / self.config.rate_limit_rps if self.config.rate_limit_rps else 1.0)
                except Exception as exc:
                    msg = f"百度搜索 query '{query[:40]}' 失败: {exc}"
                    errors.append(msg)
                    logger.error("Baidu Qianfan search error for source %s: %s",
                                 self.config.id, exc)

        logger.info("Baidu Qianfan: %d items, %d errors for source %s",
                    len(items), len(errors), self.config.id)
        return result(self._new_run_id(), self.config.id, items[:max_items], errors)


def _build_domain_filter(categories: list | None) -> list[str] | None:
    if not categories:
        return None
    domain_map = {
        "trade": ["wto.org", "trade.ec.europa.eu", "customs.gov.cn", "mofcom.gov.cn"],
        "regulation": ["eur-lex.europa.eu", "federalregister.gov", "gov.cn"],
        "china_official": ["gov.cn", "customs.gov.cn", "mofcom.gov.cn"],
        "finance": ["reuters.com", "bloomberg.com", "ft.com"],
    }
    domains = []
    for cat in categories:
        domains.extend(domain_map.get(cat, []))
    return list(set(domains)) if domains else None


def _extract_baidu_records(data) -> list[dict]:
    direct_keys = (
        "results", "search_results", "references", "items", "documents",
        "web_search_results", "data",
    )
    if isinstance(data, dict):
        for key in direct_keys:
            value = data.get(key)
            if isinstance(value, list) and any(isinstance(x, dict) for x in value):
                return [x for x in value if isinstance(x, dict)]
            if isinstance(value, dict):
                nested = _extract_baidu_records(value)
                if nested:
                    return nested

    found: list[dict] = []

    def walk(obj):
        if len(found) >= 50:
            return
        if isinstance(obj, dict):
            if any(k in obj for k in ("title", "url", "link", "content", "summary", "snippet")):
                found.append(obj)
                return
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(data)
    return found


def _first_text(record: dict, keys: list[str]) -> str:
    for key in keys:
        value = record.get(key)
        if value is None:
            continue
        if isinstance(value, (dict, list)):
            continue
        text = str(value).strip()
        if text:
            return text
    return ""
