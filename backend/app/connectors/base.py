"""
Base connector framework for GatherInfo.

Each connector handles one information channel type.
New channels are added by subclassing BaseCollector and registering with @register_collector.
"""
from __future__ import annotations

import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from uuid import uuid4

from app.models import JobStatus, SourceConfig, CollectionRun


def _content_id(source_id: str, title: str, url: str | None) -> str:
    """Deterministic content ID: SHA-256 of source|title|url, truncated to 16 hex chars."""
    base = f"{source_id}|{title}|{url or ''}"
    return hashlib.sha256(base.encode()).hexdigest()[:16]


@dataclass
class FetchItem:
    """One fetched result from a connector. Lightweight, serialization-friendly."""

    title: str
    content: str | None = None
    url: str | None = None
    summary: str | None = None
    published_at: str | None = None

    # Classification
    category: str | None = None
    language: str | None = None

    # Tag candidates (connector best-effort; engine applies topic auto-tag rules)
    suggested_tags: list[str] = field(default_factory=list)

    # Entity extraction hints
    entities: dict | None = None

    # Quality
    quality_score: float = 0.0
    relevance_score: float = 0.0

    # Raw connector output
    raw_metadata: dict | None = None

    def item_id(self, source_id: str) -> str:
        return _content_id(source_id, self.title, self.url)


@dataclass
class CollectResult:
    """Aggregate result from one collection invocation."""
    run_id: str
    source_id: str
    status: JobStatus
    items: list[FetchItem]
    discovered_urls: tuple[str, ...] = ()
    items_new: int = 0
    items_updated: int = 0
    items_failed: int = 0
    items_discovered: int = 0
    items_date_rejected: int = 0
    items_topic_rejected: int = 0
    items_quality_rejected: int = 0
    items_reused: int = 0
    items_duplicate: int = 0
    model_failures: int = 0
    source_failures: int = 0
    duration_ms: int = 0
    error_log: list[str] | None = None


class BaseCollector(ABC):
    """
    Pluggable collector base class.

    Subclass for each channel: RSSCollector, TavilyCollector, WebScrapeCollector, etc.
    """

    channel: str   # set by subclass, matches SourceChannel enum

    def __init__(self, config: SourceConfig):
        self.config = config
        self.window_start: datetime | None = None
        self.window_end: datetime | None = None
        self.target_urls: tuple[str, ...] = ()
        self.target_urls_mode = "discovery"

    def set_collection_window(
        self,
        window_start: datetime | None,
        window_end: datetime | None,
    ) -> None:
        """Attach a topic publication window for connectors that support server-side filtering."""
        self.window_start = window_start
        self.window_end = window_end

    def set_target_urls(
        self,
        urls: list[str] | tuple[str, ...] | None,
        *,
        mode: str = "discovery",
    ) -> None:
        """Attach user-configured detail pages without changing source config."""
        self.target_urls = tuple(dict.fromkeys(
            str(url).strip() for url in (urls or ()) if str(url).strip()
        ))
        self.target_urls_mode = "explicit" if mode == "explicit" else "discovery"

    @abstractmethod
    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        """Execute one fetch against the source. Called by CollectionEngine."""
        ...

    async def validate(self) -> bool:
        """Quick connectivity check. Returns True if source is reachable."""
        return True

    def _new_run_id(self) -> str:
        return f"run-{uuid4().hex[:12]}"

    async def execute(
        self,
        run: CollectionRun,
        keywords: list[str],
        max_items: int | None = None,
    ) -> CollectResult:
        """Full lifecycle: fetch → populate run record → return result."""
        start = time.monotonic()
        run.status = JobStatus.RUNNING
        run.started_at = datetime.now(timezone.utc)

        try:
            result = await self.fetch(
                keywords,
                max_items=max_items or self.config.max_items_per_run,
            )
        except Exception as exc:
            run.status = JobStatus.FAILED
            run.completed_at = datetime.now(timezone.utc)
            run.duration_ms = int((time.monotonic() - start) * 1000)
            run.error_log = [str(exc)]
            return CollectResult(
                run_id=run.id, source_id=run.source_id,
                status=JobStatus.FAILED, items=[],
                duration_ms=run.duration_ms, error_log=[str(exc)],
            )

        retrieved_at = datetime.now(timezone.utc).isoformat()
        result = replace(result, items=[
            replace(item, raw_metadata={
                **dict(item.raw_metadata or {}),
                "primary_source_url": (
                    dict(item.raw_metadata or {}).get("primary_source_url")
                    or item.url
                ),
                "publisher": (
                    dict(item.raw_metadata or {}).get("publisher")
                    or self.config.name
                ),
                "collection_entrypoint": (
                    self.config.api_endpoint or self.config.base_url
                    or self.config.homepage_url
                ),
                "retrieved_at": retrieved_at,
                "locator": dict(item.raw_metadata or {}).get("locator") or {
                    "page": None, "section": None,
                    "paragraph": None, "table_row": None,
                },
            })
            for item in result.items
        ])

        run.items_found = len(result.items)
        run.items_new = result.items_new
        run.items_failed = result.items_failed
        run.completed_at = datetime.now(timezone.utc)
        run.duration_ms = int((time.monotonic() - start) * 1000)
        run.error_log = result.error_log
        run.status = result.status
        result.run_id = run.id
        result.source_id = run.source_id
        result.duration_ms = run.duration_ms
        return result


# ── Registry ─────────────────────────────────────────────────────────────────

class ConnectorRegistry:
    """Global registry: channel name → collector class."""

    _collectors: dict[str, type[BaseCollector]] = {}

    @classmethod
    def register(cls, channel: str):
        """Class decorator to register a collector."""
        def wrapper(klass: type[BaseCollector]):
            cls._collectors[channel] = klass
            return klass
        return wrapper

    @classmethod
    def get(cls, channel: str) -> type[BaseCollector] | None:
        return cls._collectors.get(channel)

    @classmethod
    def create(cls, config: SourceConfig) -> BaseCollector:
        kls = cls.get(config.channel.value if hasattr(config.channel, 'value') else config.channel)
        if kls is None:
            raise ValueError(f"No collector for channel {config.channel}")
        return kls(config)

    @classmethod
    def available_channels(cls) -> list[str]:
        return list(cls._collectors.keys())


register_collector = ConnectorRegistry.register
