"""Prompt-oriented web research connector.

The connector aggregates Tavily and optional Baidu Qianfan web search.  A
cloud model can later populate ``planned_queries`` in ``auth_config``; until
then, it transparently uses the topic's own keyword list as the research plan.
"""
from __future__ import annotations

import logging
from types import SimpleNamespace

from app.connectors.base import (
    BaseCollector, CollectResult, FetchItem, JobStatus, SourceConfig,
    register_collector,
)
from app.connectors._helpers import result
from app.connectors.tavily_search import TavilyCollector


logger = logging.getLogger(__name__)


@register_collector("ai_research")
class AIResearchCollector(BaseCollector):
    """Search public web sources through configured search providers.

    This connector deliberately does not treat model output as evidence. Every
    returned record originates from Tavily or Baidu and keeps the source URL.
    """

    channel = "ai_research"

    def __init__(self, config: SourceConfig):
        super().__init__(config)
        self.auth_config = config.auth_config or {}

    async def validate(self) -> bool:
        if not self.config.api_key:
            return False
        tavily = TavilyCollector(self._provider_config("tavily", self.config.api_key))
        return await tavily.validate()

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        queries = self._resolve_queries(keywords)
        if not queries:
            return CollectResult(
                run_id=self._new_run_id(), source_id=self.config.id,
                status=JobStatus.FAILED, items=[], error_log=["No research queries configured"],
            )

        items: list[FetchItem] = []
        errors: list[str] = []
        providers = self.auth_config.get("search_providers") or ["tavily", "baidu_qianfan"]
        per_provider = max(1, max_items // max(1, len(providers)))

        if "tavily" in providers:
            try:
                tavily = TavilyCollector(self._provider_config("tavily", self.config.api_key))
                response = await tavily.fetch(queries, per_provider)
                items.extend(self._annotate(response.items, "tavily"))
                errors.extend(response.error_log or [])
            except Exception as exc:
                errors.append(f"Tavily research failed: {exc}")

        if "baidu_qianfan" in providers:
            baidu_key = self._resolve_baidu_api_key()
            if not baidu_key:
                logger.info("Baidu search is pending API Key configuration; skipping provider")
            else:
                try:
                    baidu = TavilyCollector(self._provider_config("baidu_qianfan", baidu_key))
                    response = await baidu.fetch(queries, per_provider)
                    items.extend(self._annotate(response.items, "baidu_qianfan"))
                    errors.extend(response.error_log or [])
                except Exception as exc:
                    errors.append(f"Baidu research failed: {exc}")

        deduped: list[FetchItem] = []
        seen: set[str] = set()
        for item in items:
            key = (item.url or item.title).strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
            if len(deduped) >= max_items:
                break

        return result(self._new_run_id(), self.config.id, deduped, errors)

    def _resolve_queries(self, keywords: list[str]) -> list[str]:
        planned = self.auth_config.get("planned_queries") or []
        values = planned if isinstance(planned, list) and planned else (keywords or self.config.default_keywords or [])
        max_queries = max(1, int(self.auth_config.get("max_queries", 8)))
        return [str(value).strip() for value in values if str(value).strip()][:max_queries]

    def _provider_config(self, provider: str, api_key: str):
        is_baidu = provider == "baidu_qianfan"
        auth_config = {
            "search_type": provider,
            "search_source": self.auth_config.get("baidu_search_source", "baidu_search_v2"),
            "resolve_published_dates": self.auth_config.get("resolve_published_dates", True),
            "max_date_resolutions": self.auth_config.get("max_date_resolutions", 30),
        }
        return SimpleNamespace(
            id=self.config.id,
            api_key=api_key,
            api_key_ref=None,
            base_url=(
                self.auth_config.get("baidu_base_url", "https://qianfan.baidubce.com")
                if is_baidu else self.config.base_url
            ),
            api_endpoint="/v2/ai_search/web_search" if is_baidu else self.config.api_endpoint,
            auth_config=auth_config,
            default_keywords=self.config.default_keywords,
            default_categories=self.config.default_categories,
            timeout_seconds=self.config.timeout_seconds,
            rate_limit_rps=self.config.rate_limit_rps,
        )

    def _resolve_baidu_api_key(self) -> str:
        direct_key = str(self.auth_config.get("baidu_api_key") or "").strip()
        if direct_key:
            return direct_key

        # Reuse the dedicated Baidu source credential so operators configure it once.
        from app.database import SessionLocal

        session = SessionLocal()
        try:
            baidu_source = session.get(SourceConfig, "baidu-search")
            return str(baidu_source.api_key or "").strip() if baidu_source else ""
        finally:
            session.close()

    def _annotate(self, items: list[FetchItem], provider: str) -> list[FetchItem]:
        for item in items:
            metadata = dict(item.raw_metadata or {})
            metadata.update({
                "research_connector": "ai_research",
                "research_provider": provider,
                "research_mode": "keyword_plan",
                # Weekly enforcement reports must not formally store a result
                # whose publication date cannot be verified.
                "allow_undated_results": False,
                "allow_unfiltered_results": True,
            })
            item.raw_metadata = metadata
        return items
