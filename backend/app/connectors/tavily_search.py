"""
Tavily Search connector for GatherInfo.
"""
import logging
import os
import asyncio
from datetime import timedelta
from urllib.parse import urlparse

import httpx
import re

from app.connectors.base import (
    BaseCollector, CollectResult, FetchItem,
    JobStatus, SourceConfig, register_collector,
)
from app.connectors._helpers import detect_lang, infer_category, build_tags, result
from app.safe_fetch import fetch_public_html, public_async_client
from app.collection_policy import evaluate_collection_policy
from app.web_content_extractor import extract_article_text

logger = logging.getLogger(__name__)

SHORT_SNIPPET_MAX_CHARS = 800


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
            or os.getenv("TAVILY_API_KEY", "")
        )
        if self.search_type in ("baidu", "baidu_qianfan"):
            self.api_key = (
                config.api_key
                or os.getenv("BAIDU_QIANFAN_API_KEY", "")
                or os.getenv("BAIDU_API_KEY", "")
            )

    async def validate(self) -> bool:
        if self.search_type in ("baidu", "baidu_qianfan"):
            return bool(self.api_key)
        if not self.api_key:
            return False
        try:
            async with public_async_client(timeout=10) as client:
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

        # Topic keywords define a topic collection. Source defaults are only a
        # fallback for standalone source collection with no supplied keywords.
        queries = keywords or self.config.default_keywords or ["global trade news"]
        items: list[FetchItem] = []
        errors: list[str] = []
        per_query = max(1, min(20, max_items // max(1, len(queries))))

        include_domains = _build_domain_filter(self.config.default_categories)
        include_domains_param = include_domains if include_domains else None
        exclude_domains = self.auth_config.get("exclude_domains") or []
        resolve_dates = self.auth_config.get("resolve_published_dates", True)
        max_date_resolutions = int(self.auth_config.get("max_date_resolutions", 40))
        include_raw_content = self.auth_config.get("include_raw_content", False)
        search_topic = self.auth_config.get("search_topic", "general")
        search_depth = self.auth_config.get("search_depth", "advanced")
        resolved_dates = 0
        policy = evaluate_collection_policy(self.config)
        allow_metadata_fetch = policy.content_depth == "full"
        allow_content_hydration = (
            allow_metadata_fetch
            and not bool(getattr(self.config, "origin_resolution_required", True))
        )
        resolve_dates = (
            self.auth_config.get("resolve_published_dates", True)
            and allow_content_hydration
        )
        hydrate_results = (
            self.auth_config.get("hydrate_search_results") is True
            and allow_content_hydration
        )
        include_raw_content = (
            self.auth_config.get("include_raw_content") is True
            and policy.llm_ingest_allowed
        )
        max_date_resolutions = int(self.auth_config.get("max_date_resolutions", 40))
        resolved_details = 0

        async with public_async_client(
            timeout=self.config.timeout_seconds,
            limits=httpx.Limits(max_connections=3),
        ) as client:
            semaphore = asyncio.Semaphore(3)
            responses = await asyncio.gather(*(
                self._request_query(
                    client, index, query, per_query,
                    include_domains_param, include_raw_content, semaphore,
                )
                for index, query in enumerate(queries)
            ))
            for query, data, request_error in responses:
                if len(items) >= max_items:
                    break
                if request_error:
                    errors.append(request_error)
                    continue
                try:
                    query_text, directives = _parse_search_query(query)

                    for r in (data or {}).get("results", []):
                        if len(items) >= max_items:
                            break
                        title = r.get("title", "")
                        search_snippet = str(r.get("content", "") or "")
                        raw_content = str(r.get("raw_content", "") or "")
                        used_raw_content = (
                            include_raw_content and len(raw_content) > len(search_snippet)
                        )
                        content = (
                            raw_content[:12_000]
                            if used_raw_content
                            else search_snippet
                        )
                        url = r.get("url", "")

                        pub_date = r.get("published_date", None)
                        if pub_date and isinstance(pub_date, str):
                            try:
                                from datetime import timezone, datetime
                                dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                                pub_date = dt.isoformat()
                            except (ValueError, TypeError):
                                pub_date = None

                        # Search results often omit the date even when the source
                        # article exposes it in structured metadata or its page.
                        # Search snippets often contain an explicit publication
                        # date; use it before spending time on a detail fetch.
                        if not pub_date:
                            # A bare date in a search snippet may belong to a
                            # navigation card or a related story. Prefer an
                            # explicitly labelled date first, then verify the
                            # page, and only use a bare snippet date last.
                            pub_date = _extract_date_hint(
                                f"{title} {search_snippet}", labelled_only=True
                            )
                        if not pub_date and content:
                            pub_date = _extract_date_hint(
                                f"{title} {content[:4000]}", labelled_only=True
                            )
                        if not pub_date and content:
                            # News search is already date-bounded by Tavily.
                            # The first part of the extracted article commonly
                            # contains its visible publication date.
                            pub_date = _extract_date_hint(
                                f"{title} {content[:1800]}"
                            )
                        page_metadata: dict = {}
                        should_fetch_detail = (resolve_dates and not pub_date) or (
                            hydrate_results and _is_short_snippet(content)
                        )
                        if (
                            url
                            and resolved_details < max_date_resolutions
                            and should_fetch_detail
                        ):
                            page_metadata = await _resolve_page_metadata(
                                client, url,
                                minimum_interval_seconds=float(
                                    getattr(self.config, "crawl_delay_seconds", 0) or 0
                                ),
                            )
                            resolved_details += 1
                        if (
                            resolve_dates
                            and not pub_date
                            and page_metadata.get("published_at")
                        ):
                            pub_date = page_metadata["published_at"]
                        if not pub_date:
                            pub_date = _extract_date_hint(f"{title} {search_snippet}")

                        summary = search_snippet[:500] if search_snippet else None
                        if (
                            hydrate_results
                            and page_metadata
                            and _is_short_snippet(content)
                        ):
                            title = _prefer_extracted_title(
                                title, str(page_metadata.get("title") or "")
                            )
                            content = _prefer_more_complete_text(
                                content, str(page_metadata.get("content") or "")
                            )
                            summary = _prefer_more_complete_text(
                                summary, str(page_metadata.get("summary") or "")
                            ) or None

                        items.append(FetchItem(
                            title=title,
                            content=content,
                            url=url,
                            published_at=pub_date,
                            summary=summary,
                            language=detect_lang(f"{url} {content}"),
                            category=infer_category(title, content),
                            suggested_tags=build_tags(title, content),
                            quality_score=r.get("score", 0.5),
                            relevance_score=r.get("score", 0.5),
                            raw_metadata={
                                "engine": "tavily",
                                "query": query_text,
                                "search_jurisdiction": directives.get("jurisdiction"),
                                "search_country": directives.get("country"),
                                "source_domain": urlparse(url).netloc.casefold(),
                                "score": r.get("score"),
                                "content_source": (
                                    "tavily_raw_content"
                                    if used_raw_content
                                    else "tavily_snippet"
                                ),
                                "allow_undated_results": False,
                                "allow_unfiltered_results": True,
                            },
                        ))

                except Exception as exc:
                    query_text, _ = _parse_search_query(query)
                    msg = f"Query '{query_text[:40]}': {exc}"
                    errors.append(msg)
                    logger.error("Tavily fetch error for source %s: %s", self.config.id, exc)

        logger.info("Tavily: %d items, %d errors for source %s",
                     len(items), len(errors), self.config.id)
        return result(self._new_run_id(), self.config.id, items, errors)

    async def _request_query(
        self,
        client: httpx.AsyncClient,
        index: int,
        query: str,
        per_query: int,
        include_domains: list[str] | None,
        include_raw_content: bool,
        semaphore: asyncio.Semaphore,
    ) -> tuple[str, dict | None, str | None]:
        interval = 1.0 / self.config.rate_limit_rps if self.config.rate_limit_rps else 1.0
        if index:
            await asyncio.sleep(index * interval)
        payload = {
            "api_key": self.api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": per_query,
            "include_answer": False,
            "include_raw_content": include_raw_content,
            "topic": self.auth_config.get("topic", "news"),
        }
        if self.window_start:
            payload["start_date"] = self.window_start.date().isoformat()
        if self.window_end:
            payload["end_date"] = (
                self.window_end.date() + timedelta(days=1)
            ).isoformat()
        if include_domains:
            payload["include_domains"] = include_domains
        try:
            async with semaphore:
                response = await client.post(self.BASE_URL, json=payload)
            if response.status_code == 429:
                logger.warning("Tavily rate limited for query: %s", query[:60])
                return query, None, f"Rate limited: {query}"
            response.raise_for_status()
            return query, response.json(), None
        except Exception as exc:
            message = f"Query '{query[:40]}': {exc}"
            logger.error("Tavily fetch error for source %s: %s", self.config.id, exc)
            return query, None, message

    async def _fetch_baidu_qianfan(
        self, keywords: list[str], max_items: int = 100
    ) -> CollectResult:
        if not self.api_key:
            return CollectResult(
                run_id=self._new_run_id(), source_id=self.config.id,
                status=JobStatus.FAILED, items=[],
                error_log=["BAIDU_QIANFAN_API_KEY not set"],
            )

        endpoint = self.config.api_endpoint or self.auth_config.get("api_endpoint") or "/v2/ai_search/web_search"
        base = (self.config.base_url or "https://qianfan.baidubce.com").rstrip("/")
        url = endpoint if endpoint.startswith("http") else base + "/" + endpoint.lstrip("/")
        queries = keywords or self.config.default_keywords or ["customs enforcement"]
        items: list[FetchItem] = []
        errors: list[str] = []
        per_query = max(1, min(10, max_items // max(1, len(queries))))
        headers = {
            "Content-Type": "application/json",
            "X-Appbuilder-Authorization": f"Bearer {self.api_key}",
            "User-Agent": "GatherInfo/0.5 (Baidu Qianfan Search)",
        }

        async with public_async_client(timeout=self.config.timeout_seconds) as client:
            for query in queries:
                if len(items) >= max_items:
                    break
                try:
                    query_text, directives = _parse_search_query(query)
                    response = await client.post(url, headers=headers, json={
                        "messages": [{"role": "user", "content": query_text}],
                        "search_source": self.auth_config.get("search_source", "baidu_search_v2"),
                        "resource_type_filter": self.auth_config.get(
                            "resource_type_filter", [{"type": "web", "top_k": 10}]
                        ),
                    })
                    if response.status_code == 401:
                        errors.append(f"Baidu authentication failed: {query}")
                        break
                    if response.status_code == 429:
                        errors.append(f"Baidu rate limited: {query}")
                        break
                    response.raise_for_status()
                    for record in _extract_baidu_records(response.json())[:per_query]:
                        title = _first_text(record, ["title", "name", "doc_title"]) or query_text
                        content = _first_text(record, ["content", "summary", "snippet", "abstract", "description"])
                        item_url = _first_text(record, ["url", "link", "href", "source_url"])
                        published_at = _first_text(record, ["published_at", "publish_time", "date", "time"])
                        text = f"{title} {content}"
                        items.append(FetchItem(
                            title=title, content=content or None, url=item_url or None,
                            published_at=published_at or None, summary=(content or "")[:500] or None,
                            language=detect_lang(text), category=infer_category(title, content),
                            suggested_tags=build_tags(title, content), quality_score=0.7,
                            relevance_score=0.7,
                            raw_metadata={
                                "engine": "baidu_qianfan", "query": query_text,
                                "search_jurisdiction": directives.get("jurisdiction"),
                                "search_country": directives.get("country"),
                                "source_domain": urlparse(item_url or "").netloc.casefold(),
                                # Each item originates from a single, already-scoped
                                # search query; do not require it to contain every
                                # keyword configured for the topic again.
                                "allow_unfiltered_results": True,
                                "allow_undated_results": False,
                            },
                        ))
                    await asyncio.sleep(1.0 / self.config.rate_limit_rps if self.config.rate_limit_rps else 1.0)
                except Exception as exc:
                    query_text, _ = _parse_search_query(query)
                    errors.append(f"Baidu search failed for '{query_text[:40]}': {exc}")
                    logger.error("Baidu Qianfan search error for source %s: %s", self.config.id, exc)

        return result(self._new_run_id(), self.config.id, items[:max_items], errors)


async def _resolve_page_metadata(
    client: httpx.AsyncClient, url: str, *, minimum_interval_seconds: float = 0,
) -> dict:
    """Read public article metadata using one ordinary GET request."""
    try:
        response = await fetch_public_html(
            client, url, timeout_seconds=15,
            minimum_interval_seconds=minimum_interval_seconds,
        )
        if response is None:
            return {}
        parsed = extract_article_text(response.text, response.url)
        published = parsed.get("published_at")
        if not published:
            # Some public pages expose a human-readable Written/Updated line
            # in the article body but omit schema.org date metadata.
            published = _extract_date_hint(
                str(parsed.get("content") or ""), labelled_only=True
            )
        if not published:
            published = _extract_url_date_hint(url)
        if not published:
            return {}
        normalized_published = _normalize_published_at(published)
        return {**parsed, "published_at": normalized_published}
    except Exception:
        return {}


def _is_short_snippet(content: str | None) -> bool:
    return len((content or "").strip()) < SHORT_SNIPPET_MAX_CHARS


def _normalize_published_at(value: object) -> str | None:
    if not value:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        ).isoformat()
    except (TypeError, ValueError):
        return None


def _extract_url_date_hint(url: str) -> str | None:
    """Extract dates encoded in common official-news URL paths."""
    from datetime import datetime, timezone

    for pattern in (
        r"/(\d{4})/(\d{1,2})/(\d{1,2})(?:/|$)",
        r"/(\d{4})(\d{2})/(\d{1,2})(?:/|$)",
    ):
        match = re.search(pattern, url or "")
        if not match:
            continue
        try:
            year, month, day = (int(value) for value in match.groups())
            return datetime(year, month, day, tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return None
def _prefer_more_complete_text(current: str | None, candidate: str | None) -> str:
    current_text = current or ""
    candidate_text = (candidate or "").strip()
    return (
        candidate_text
        if len(candidate_text) > len(current_text.strip())
        else current_text
    )


def _prefer_extracted_title(current: str, candidate: str) -> str:
    """Use a longer page title only when it retains the search-result title."""
    current_text = current
    candidate_text = candidate.strip()
    if not current_text.strip():
        return candidate_text
    if len(candidate_text) <= len(current_text.strip()):
        return current_text
    normalized_current = " ".join(current_text.casefold().split())
    normalized_candidate = " ".join(candidate_text.casefold().split())
    return candidate_text if normalized_current in normalized_candidate else current_text

def _parse_search_query(query: str) -> tuple[str, dict[str, str]]:
    """Split optional research directives from the query sent to providers."""
    raw = str(query or "").strip()
    if "||" not in raw:
        return raw, {}
    directive_text, query_text = raw.split("||", 1)
    directives: dict[str, str] = {}
    for entry in directive_text.split(";"):
        if "=" not in entry:
            continue
        key, value = entry.split("=", 1)
        key = key.strip().casefold()
        value = value.strip()
        if key in {"country", "jurisdiction"} and value:
            directives[key] = value
    return query_text.strip(), directives

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


def _extract_date_hint(text: str, labelled_only: bool = False) -> str | None:
    """Extract explicit dates from search snippets when structured metadata is absent."""
    from datetime import datetime, timezone

    # Prefer dates explicitly labelled as publication/writing/update dates.
    # This avoids mistaking a site's navigation date for the article date.
    labelled = re.search(
        r"(?:published|publication date|posted|written|updated|date|发布时间|发表|撰写|更新)"
        r"[^0-9]{0,32}(\d{4}[-/]\d{1,2}[-/]\d{1,2}|"
        r"[A-Z][a-z]{2,8}\s+\d{1,2},\s+\d{4}|"
        r"\d{1,2}\s+[A-Z][a-z]{2,8}\s+\d{4})",
        text or "",
        flags=re.IGNORECASE,
    )
    labelled_value = labelled.group(1) if labelled else None
    if labelled_only and not labelled_value:
        return None
    patterns = (
        r"\b(\d{4}-\d{1,2}-\d{1,2})\b",
        r"\b(\d{4}/\d{1,2}/\d{1,2})\b",
        r"\b([A-Z][a-z]{2,8}\s+\d{1,2},\s+\d{4})\b",
        r"\b([A-Z][a-z]{2,8}\s+\d{1,2}\s+\d{4})\b",
        r"\b(\d{1,2}\s+[A-Z][a-z]{2,8}\s+\d{4})\b",
    )
    formats = (
        "%Y-%m-%d", "%Y/%m/%d",
        "%B %d, %Y", "%b %d, %Y", "%B %d %Y", "%b %d %Y",
        "%d %B %Y", "%d %b %Y",
    )
    values = [labelled_value] if labelled_value else []
    if not labelled_value:
        for pattern in patterns:
            match = re.search(pattern, text or "")
            if match:
                values.append(match.group(1))
    for value in values:
        if not value:
            continue
        for fmt in formats:
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc).isoformat()
            except ValueError:
                continue
    return None


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
