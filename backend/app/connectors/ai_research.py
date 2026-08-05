"""Prompt-oriented web research connector.

The connector aggregates search APIs and key-free official enforcement
indexes. A cloud model can populate ``planned_queries`` in ``auth_config``;
until then, it transparently uses the topic's own keyword list as the plan.
"""
from __future__ import annotations

import asyncio
import logging
import math
from dataclasses import replace
from types import SimpleNamespace

from app.connectors.base import (
    BaseCollector, CollectResult, FetchItem, JobStatus, SourceConfig,
    register_collector,
)
from app.connectors._helpers import result
from app.connectors.gdelt_search import GDELTSearchCollector
from app.connectors.official_enforcement_search import (
    OfficialEnforcementSearchCollector,
)
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
        providers = self.auth_config.get("search_providers") or [
        "tavily", "baidu_qianfan", "official_enforcement", "gdelt",
        ]
        is_enforcement_plan = any(
            str(query).lstrip().startswith("jurisdiction=") for query in queries
        )
        per_provider = max(1, max_items // max(1, len(providers)))
        provider_tasks = []
        if "tavily" in providers:
            provider_tasks.append(
                self._fetch_provider(
                    "tavily", self.config.api_key, queries,
                    max_items if is_enforcement_plan else per_provider,
                    is_enforcement_plan=is_enforcement_plan,
                )
            )
        if "baidu_qianfan" in providers:
            baidu_key = self._resolve_baidu_api_key()
            if baidu_key:
                provider_tasks.append(
                    self._fetch_provider(
                        "baidu_qianfan", baidu_key, queries,
                        max_items if is_enforcement_plan else per_provider,
                        is_enforcement_plan=is_enforcement_plan,
                    )
                )
            else:
                logger.info("Baidu search is pending API Key configuration; skipping provider")
        if "gdelt" in providers:
            provider_tasks.append(
                self._fetch_provider(
                    "gdelt", "", queries, per_provider,
                    is_enforcement_plan=is_enforcement_plan,
                )
            )
        if "official_enforcement" in providers:
            provider_tasks.append(
                self._fetch_provider(
                    # Official adapters are high-signal and key-free. Do not
                    # divide their result budget with rate-limited web APIs.
                    "official_enforcement", "", queries, max_items,
                    is_enforcement_plan=is_enforcement_plan,
                )
            )

        provider_results = await asyncio.gather(*provider_tasks, return_exceptions=True)
        provider_item_groups: list[list[FetchItem]] = []
        for provider_result in provider_results:
            if isinstance(provider_result, Exception):
                errors.append(f"Search provider failed: {provider_result}")
                continue
            provider_items, provider_errors = provider_result
            provider_item_groups.append(provider_items)
            errors.extend(provider_errors)
        if is_enforcement_plan:
            # Keep one high-volume provider from crowding official and regional
            # search results out of the model-review pool.
            pending_groups = [list(group) for group in provider_item_groups if group]
            while pending_groups and len(items) < max_items:
                next_groups: list[list[FetchItem]] = []
                for group in pending_groups:
                    if group:
                        items.append(group.pop(0))
                    if group:
                        next_groups.append(group)
                    if len(items) >= max_items:
                        break
                pending_groups = next_groups
        else:
            for provider_items in provider_item_groups:
                items.extend(provider_items)

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

    async def _fetch_provider(
        self,
        provider: str,
        api_key: str,
        queries: list[str],
        max_items: int,
        *,
        is_enforcement_plan: bool = False,
    ) -> tuple[list[FetchItem], list[str]]:
        shard_count = (
            1 if provider in {"gdelt", "official_enforcement"}
            else 3 if len(queries) >= 18
            else 2 if len(queries) >= 12
            else 1
        )
        shards = [queries[index::shard_count] for index in range(shard_count)]
        per_shard_items = max(1, math.ceil(max_items / shard_count))
        total_date_resolutions = max(
            0, int(self.auth_config.get("max_date_resolutions", 8))
        )

        async def fetch_shard(shard: list[str]):
            provider_config = self._provider_config(
                provider, api_key, is_enforcement_plan=is_enforcement_plan,
            )
            provider_config.auth_config = dict(provider_config.auth_config)
            provider_config.auth_config["max_date_resolutions"] = math.ceil(
                total_date_resolutions / shard_count
            )
            collector_class = {
                "gdelt": GDELTSearchCollector,
                "official_enforcement": OfficialEnforcementSearchCollector,
            }.get(provider, TavilyCollector)
            collector = collector_class(provider_config)
            collector.set_collection_window(self.window_start, self.window_end)
            return await collector.fetch(shard, per_shard_items)

        responses = await asyncio.gather(
            *[fetch_shard(shard) for shard in shards if shard],
            return_exceptions=True,
        )
        items: list[FetchItem] = []
        errors: list[str] = []
        for response in responses:
            if isinstance(response, Exception):
                errors.append(f"{provider} shard failed: {response}")
                continue
            items.extend(self._annotate(response.items, provider))
            errors.extend(response.error_log or [])
        return items[:max_items], errors

    def _resolve_queries(self, keywords: list[str]) -> list[str]:
        planned = self.auth_config.get("planned_queries") or []
        values = planned if isinstance(planned, list) and planned else (keywords or self.config.default_keywords or [])
        configured_limit = max(1, int(self.auth_config.get("max_queries", 8)))
        # A geographic research plan may deliberately contain more missions
        # than the source's historical generic-query limit.
        max_queries = max(configured_limit, min(len(values), 40))
        return [str(value).strip() for value in values if str(value).strip()][:max_queries]

    def _provider_config(
        self, provider: str, api_key: str, *, is_enforcement_plan: bool = False,
    ):
        is_baidu = provider == "baidu_qianfan"
        auth_config = {
            "search_type": provider,
            "search_source": self.auth_config.get("baidu_search_source", "baidu_search_v2"),
            "resolve_published_dates": self.auth_config.get("resolve_published_dates", True),
            "max_date_resolutions": self.auth_config.get("max_date_resolutions", 30),
            "include_raw_content": (
                True if is_enforcement_plan
                else self.auth_config.get("include_raw_content", False)
            ),
            "search_topic": self.auth_config.get("search_topic", "news"),
            "search_depth": (
                "advanced" if is_enforcement_plan
                else self.auth_config.get("search_depth", "basic")
            ),
            "exclude_domains": self.auth_config.get(
                "exclude_domains",
                [
                    "customs.gov.cn", "renrendoc.com", "doc88.com",
                    "wenku.baidu.com", "baike.baidu.com", "baijiahao.baidu.com",
                ],
            ),
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
        annotated: list[FetchItem] = []
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
            annotated.append(replace(item, raw_metadata=metadata))
        return annotated
