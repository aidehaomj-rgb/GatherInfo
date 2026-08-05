"""
Generic JSON-API connector for GatherInfo.

A single configurable connector that can talk to most JSON HTTP APIs
(NewsAPI, UN Comtrade, World Bank, Trading Economics, etc.) so the user
only configures things in ONE place (this project), per source.

All behaviour is driven by SourceConfig fields.
"""
import logging
from datetime import timezone
from urllib.parse import urljoin, urlsplit

from app.connectors.base import (
    BaseCollector, CollectResult, FetchItem,
    JobStatus, SourceConfig, register_collector,
)
from app.safe_fetch import fetch_public_json, public_async_client

logger = logging.getLogger(__name__)


@register_collector("json_api")
class JsonApiCollector(BaseCollector):
    channel = "json_api"

    async def validate(self) -> bool:
        ac = self.config.auth_config or {}
        if ac.get("auth", "none") != "none" and not self.config.api_key:
            return False
        url = self._request_url()
        if not url:
            return False
        if self._credential_transport_error(url):
            return False
        try:
            async with public_async_client(timeout=10) as client:
                params, headers, _ = self._build_request(["test"])
                response = await fetch_public_json(
                    client, url, params=params, headers=headers, timeout_seconds=10,
                )
                return bool(response and response.status_code < 500)
        except Exception:
            return False

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        url = self._request_url()
        if not url:
            return self._error("base_url / api_endpoint not configured")

        ac = self.config.auth_config or {}
        if ac.get("auth", "none") != "none" and not self.config.api_key:
            logger.warning("api_key not configured for JSON API source %s", self.config.id)
            return self._error("api_key not configured for this source")
        transport_error = self._credential_transport_error(url)
        if transport_error:
            return self._error(transport_error)

        method = (ac.get("method") or "GET").upper()
        queries = self._query_terms(keywords)
        params, headers, body = self._build_request(queries)

        items: list[FetchItem] = []
        errors: list[str] = []
        try:
            async with public_async_client(timeout=self.config.timeout_seconds) as client:
                response = await fetch_public_json(
                    client,
                    url,
                    method=method,
                    params=params,
                    headers=headers,
                    json_body=body if method == "POST" else None,
                    timeout_seconds=self.config.timeout_seconds,
                    minimum_interval_seconds=max(
                        float(getattr(self.config, "crawl_delay_seconds", 0) or 0),
                        1.0 / float(self.config.rate_limit_rps or 1),
                    ),
                )
                if response and response.status_code == 429:
                    logger.warning("JSON API rate limited for source %s", self.config.id)
                    return self._error("Rate limited (HTTP 429)")
                if response is None:
                    return self._error("Unsafe, redirected, oversized, or non-JSON API response")
                data = response.data
        except Exception as exc:
            logger.error("JSON API HTTP error for source %s: %s", self.config.id, exc)
            return self._error(f"HTTP/JSON error: {exc}")

        records = _dig(data, ac.get("items_path", ""))
        if records is None:
            records = data if isinstance(data, list) else []
        if not isinstance(records, list):
            msg = f"items_path did not resolve to a list: {ac.get('items_path')}"
            logger.warning("JSON API parse issue for source %s: %s", self.config.id, msg)
            return self._error(msg)

        fields = ac.get("fields") or {
            "title": "title", "content": "content", "summary": "description",
            "url": "url", "published_at": "publishedAt",
            "language": "language", "category": "category",
        }
        for rec in records[:max_items]:
            if not isinstance(rec, dict):
                continue
            title = _coerce_str(_dig(rec, fields.get("title", "title")))
            if not title:
                continue
            content = _coerce_str(_dig(rec, fields.get("content", "content")))
            summary = _coerce_str(_dig(rec, fields.get("summary", "summary")))
            items.append(FetchItem(
                title=title,
                content=content or summary or None,
                url=_coerce_str(_dig(rec, fields.get("url", "url"))) or None,
                summary=(summary or content or "")[:500] or None,
                published_at=_coerce_str(
                    _dig(rec, fields.get("published_at", "publishedAt"))) or None,
                language=_coerce_str(
                    _dig(rec, fields.get("language", "language"))) or None,
                category=_coerce_str(
                    _dig(rec, fields.get("category", "category"))) or None,
                raw_metadata={"connector": "json_api", "source": self.config.id},
            ))

        logger.info("JSON API: %d items for source %s", len(items), self.config.id)
        return CollectResult(
            run_id=self._new_run_id(), source_id=self.config.id,
            status=JobStatus.COMPLETED, items=items, items_new=len(items),
        )

    def _request_url(self) -> str:
        base = (self.config.base_url or "").strip()
        endpoint = (self.config.api_endpoint or "").strip()
        if endpoint.startswith("http"):
            return endpoint
        if base and endpoint:
            return urljoin(base if base.endswith("/") else base + "/",
                           endpoint.lstrip("/"))
        return base or endpoint

    def _build_request(self, queries: list[str]) -> tuple[dict, dict, dict]:
        ac = self.config.auth_config or {}
        params: dict = dict(ac.get("query") or {})
        headers: dict = {"Accept": "application/json",
                         "User-Agent": "GatherInfo/0.4 (Customs Intel Monitor)"}
        body: dict = dict(ac.get("body") or {})

        kw = [q for q in queries if q]
        if kw:
            joined = (ac.get("keyword_join") or " OR ").join(kw)
            kp = ac.get("keyword_param")
            if kp:
                if (ac.get("method") or "GET").upper() == "POST" and ac.get(
                        "keyword_in") == "body":
                    body[kp] = joined
                else:
                    params[kp] = joined

        window_format = str(ac.get("window_date_format") or "%Y-%m-%d")
        window_start_param = ac.get("window_start_param")
        window_end_param = ac.get("window_end_param")
        if window_start_param and self.window_start:
            params[str(window_start_param)] = self.window_start.astimezone(
                timezone.utc
            ).strftime(window_format)
        if window_end_param and self.window_end:
            params[str(window_end_param)] = self.window_end.astimezone(
                timezone.utc
            ).strftime(window_format)

        auth = ac.get("auth", "none")
        key = self.config.api_key or ""
        if auth == "query" and key:
            params[ac.get("auth_param", "apiKey")] = key
        elif auth == "header" and key:
            headers[ac.get("auth_param", "X-Api-Key")] = key
        elif auth == "bearer" and key:
            headers["Authorization"] = f"Bearer {key}"

        return params, headers, body

    def _query_terms(self, topic_keywords: list[str]) -> list[str]:
        defaults = self.config.default_keywords or []
        if (self.config.auth_config or {}).get("prefer_default_keywords") and defaults:
            return list(defaults)
        return list(topic_keywords or defaults or [""])

    def _credential_transport_error(self, url: str) -> str | None:
        auth = str((self.config.auth_config or {}).get("auth", "none"))
        if auth == "none" or not self.config.api_key:
            return None
        try:
            scheme = urlsplit(url).scheme.casefold()
        except ValueError:
            return "API credential target URL is invalid"
        if scheme != "https":
            return "API credentials require an HTTPS endpoint"
        return None

    def _error(self, msg: str) -> CollectResult:
        return CollectResult(
            run_id=self._new_run_id(), source_id=self.config.id,
            status=JobStatus.FAILED, items=[], error_log=[msg],
        )


def _dig(obj, path: str):
    if path is None or path == "":
        return obj
    cur = obj
    for part in str(path).split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
        if cur is None:
            return None
    return cur


def _coerce_str(val) -> str:
    if val is None:
        return ""
    if isinstance(val, str):
        return val.strip()
    if isinstance(val, (int, float, bool)):
        return str(val)
    if isinstance(val, dict):
        for k in ("name", "value", "text", "title"):
            if k in val:
                return _coerce_str(val[k])
    if isinstance(val, list):
        return ", ".join(_coerce_str(v) for v in val if v is not None)
    return str(val)
