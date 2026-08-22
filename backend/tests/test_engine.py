"""
Tests for the collection engine — keyword filtering, dedup, persistence, auto-tagging.

Run: cd backend && python -m pytest tests/test_engine.py -v
"""
import os
import sys
import pytest
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch, AsyncMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Ensure the backend package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine import (
    CollectionEngine, MAX_CANDIDATES_PER_SOURCE,
    SOURCE_EXECUTION_TIMEOUT_SECONDS, utc_now, _hash,
    _canonical_source_url, _dedupe_fingerprint,
    _sync_run_result_metrics,
    _source_provenance,
    _planning_window_dates, _planning_window_days, _topic_collection_window,
)
from app.connectors.base import FetchItem, CollectResult
from app.database import Base
from app.models import (
    CollectedItem, CollectionRun, ItemStatus, JobStatus, SourceChannel,
    SourceConfig, Topic,
)


def _allow_full_collection(source):
    source.is_configured = True
    source.verification_status = "verified"
    source.robots_status = "allowed"
    source.terms_status = "public_domain"
    source.llm_ingest_allowed = True
    return source


def test_hash_deterministic():
    """_hash returns the same output for the same input."""
    assert _hash("hello") == _hash("hello")
    assert _hash("hello") != _hash("world")
    assert len(_hash("test")) == 64  # SHA-256 hex


def test_dedupe_fingerprint_preserves_curated_roundup_section_identity():
    first = _dedupe_fingerprint(
        "https://example.test/daily?traderadar_section=abc123&utm_source=x",
        "First section", "content",
    )
    second = _dedupe_fingerprint(
        "https://example.test/daily?traderadar_section=def456",
        "Second section", "content",
    )

    assert first == "url:https://example.test/daily?traderadar_section=abc123"
    assert second == "url:https://example.test/daily?traderadar_section=def456"
    assert first != second


def test_canonical_source_url_strips_tracking_but_keeps_evidence_query():
    assert _canonical_source_url(
        "HTTPS://Example.COM/news/?id=42&utm_source=x&fbclid=y#fragment"
    ) == "https://example.com/news?id=42"


def test_final_run_metrics_include_window_and_quality_rejections():
    run = SimpleNamespace(items_new=0, items_failed=0, error_log=None)
    result = CollectResult(
        run_id="run-1", source_id="source-1", status=JobStatus.COMPLETED,
        items=[], items_new=2, items_failed=7,
        error_log=["采集窗口过滤 3 条", "质量审核拒绝 4 条"],
    )

    _sync_run_result_metrics(run, result, persisted_count=2)

    assert run.items_new == 2
    assert run.items_failed == 7
    assert run.error_log == ["采集窗口过滤 3 条", "质量审核拒绝 4 条"]


def test_hash_empty_string():
    """_hash handles empty string."""
    result = _hash("")
    assert isinstance(result, str)
    assert len(result) == 64


def test_record_progress_appends_an_immutable_timestamped_event():
    mock_db = MagicMock()
    engine = CollectionEngine(mock_db)
    original_events = [{"stage": "queued", "message": "任务已创建"}]
    run = MagicMock(spec=CollectionRun)
    run.progress_events = original_events

    engine._record_progress(
        run,
        stage="discover",
        message="发现信息：《测试文章》",
        item_title="测试文章",
        detail={"url": "https://example.com/article"},
    )

    assert run.progress_events is not original_events
    assert original_events == [{"stage": "queued", "message": "任务已创建"}]
    assert run.progress_events[-1]["stage"] == "discover"
    assert run.progress_events[-1]["item_title"] == "测试文章"
    assert run.progress_events[-1]["detail"]["url"] == "https://example.com/article"
    assert run.progress_events[-1]["created_at"]
    mock_db.commit.assert_called_once()


def test_weekly_topic_collection_uses_current_beijing_week_window() -> None:
    now = datetime(2026, 8, 4, 4, 30, tzinfo=timezone.utc)
    topic = SimpleNamespace(weekly_digest_enabled=True, collect_window_days=30)

    start, end = _topic_collection_window(topic, now=now)

    assert start == datetime(2026, 8, 2, 16, tzinfo=timezone.utc)
    assert end == now


def test_query_planner_uses_resolved_week_span_instead_of_topic_30_days() -> None:
    start = datetime(2026, 8, 2, 16, tzinfo=timezone.utc)
    current = datetime(2026, 8, 4, 0, 15, tzinfo=timezone.utc)
    complete_week_end = datetime(2026, 8, 9, 16, tzinfo=timezone.utc)

    assert _planning_window_days(start, current, fallback_days=30) == 2
    assert _planning_window_days(start, complete_week_end, fallback_days=30) == 7
    assert _planning_window_dates(start, complete_week_end) == (
        datetime(2026, 8, 3).date(), datetime(2026, 8, 9).date(),
    )


def test_resolve_sources_skips_channels_without_registered_connector() -> None:
    sql_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(sql_engine)
    db = sessionmaker(bind=sql_engine)()
    try:
        db.add_all([
            Topic(
                id="topic-connectors", name="连接器核验",
                source_ids=["supported-web", "unsupported-social"],
            ),
            SourceConfig(
                id="supported-web", name="网页源",
                channel=SourceChannel.WEB_SCRAPE, base_url="https://cbp.gov/newsroom",
                is_active=True, is_configured=True, verification_status="verified",
                robots_status="allowed", terms_status="public_domain",
                llm_ingest_allowed=True,
            ),
            SourceConfig(
                id="unsupported-social", name="社交源",
                channel=SourceChannel.SOCIAL, base_url="https://example.com/social",
                is_active=True, is_configured=True, verification_status="verified",
                robots_status="allowed", terms_status="public_domain",
                llm_ingest_allowed=True,
            ),
        ])
        db.commit()
        topic = db.query(Topic).filter(Topic.id == "topic-connectors").one()

        resolved = CollectionEngine(db)._resolve_sources(topic)

        assert [source.id for source in resolved] == ["supported-web"]
    finally:
        db.close()
        sql_engine.dispose()


class TestFetchItemId:
    """FetchItem.item_id generates unique IDs."""
    
    def test_item_id_format(self):
        fi = FetchItem(title="Test", url="http://example.com/1", content="body")
        item_id = fi.item_id("src-1")
        assert isinstance(item_id, str)
        assert len(item_id) > 0

    def test_item_id_same_input_same_output(self):
        fi1 = FetchItem(title="A", url="http://x.com", content="c")
        fi2 = FetchItem(title="A", url="http://x.com", content="c")
        assert fi1.item_id("s1") == fi2.item_id("s1")

    def test_item_id_different_content_different_output(self):
        fi1 = FetchItem(title="A", url="http://x.com/1", content="c1")
        fi2 = FetchItem(title="A", url="http://x.com/2", content="c2")
        assert fi1.item_id("s1") != fi2.item_id("s1")


def test_collection_fails_source_when_connector_exceeds_timeout(monkeypatch):
    """A slow website must not block the entire topic queue indefinitely."""
    mock_db = MagicMock()
    source = MagicMock()
    source.id = "slow-source"
    source.name = "Slow source"
    source.is_active = True
    source.max_items_per_run = 1
    _allow_full_collection(source)
    mock_db.query.return_value.filter.return_value.first.return_value = source
    connector = MagicMock()

    async def never_finishes(*_args, **_kwargs):
        await __import__("asyncio").sleep(SOURCE_EXECUTION_TIMEOUT_SECONDS + 1)

    connector.execute = never_finishes
    monkeypatch.setattr("app.engine.SOURCE_EXECUTION_TIMEOUT_SECONDS", 0.01)
    monkeypatch.setattr("app.engine.ConnectorRegistry.create", lambda _source: connector)
    engine = CollectionEngine(mock_db)

    import asyncio
    result = asyncio.run(engine.collect_from_source("slow-source", ["risk"], "topic-1"))

    assert result.status == JobStatus.FAILED
    assert "超过" in result.error_log[0]


class TestPersistItems:
    """_persist_items keyword filtering and dedup logic."""

    def test_keyword_filtering_requires_match(self):
        """Items that don't match keywords should be skipped."""
        # This test uses mock DB to verify filter logic
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        items = [
            FetchItem(title="Irrelevant news", content="Nothing to see here", url="http://a.com"),
        ]
        keywords = ["tariff", "trade"]

        engine._persist_items(items, "src-1", "run-1", topic_id="t1",
                              keywords=keywords)

        # Should not add anything because no keyword matches
        mock_db.add.assert_not_called()

    def test_strict_topic_window_does_not_infer_date_from_article_text(self):
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        item = FetchItem(
            title="Tariff notice dated 2026-08-10",
            content="Tariff customs implementation details " * 20,
            url="https://example.gov/notice?utm_source=test",
        )

        engine._persist_items(
            [item], "src-1", "run-1", topic_id="global-trade",
            window_start=datetime(2026, 8, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 8, 17, tzinfo=timezone.utc),
            keywords=["tariff"], strict_date_metadata=True,
        )

        mock_db.add.assert_not_called()

    def test_source_provenance_preserves_playbook_evidence_locator(self):
        item = FetchItem(
            title="Tariff notice",
            url="https://example.gov/news?id=7&utm_source=noise",
            published_at="2026-08-10T00:00:00+00:00",
            raw_metadata={
                "primary_source_url": "https://agency.gov/original/7",
                "discovery_url": "https://search.example/result",
                "publisher": "Agency",
                "locator": {"section": "press releases", "paragraph": 3},
                "retrieved_at": "2026-08-17T01:02:03+00:00",
                "attachment_urls": ["https://agency.gov/file.pdf"],
            },
        )

        provenance = _source_provenance(
            item,
            datetime(2026, 8, 10, tzinfo=timezone.utc),
            "hash-value",
        )

        assert _canonical_source_url(item.url) == "https://example.gov/news?id=7"
        assert provenance["primary_source_url"] == "https://agency.gov/original/7"
        assert provenance["discovery_url"] == "https://search.example/result"
        assert provenance["locator"]["section"] == "press releases"
        assert provenance["locator"]["paragraph"] == 3
        assert provenance["retrieved_at"] == "2026-08-17T01:02:03+00:00"
        assert provenance["attachment_urls"] == ["https://agency.gov/file.pdf"]

    def test_keyword_filtering_allows_match(self):
        """Items matching enough keywords should be persisted."""
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        items = [
            FetchItem(title="Tariff trade war update", content="trade war escalates", url="http://a.com"),
        ]
        keywords = ["tariff", "trade"]

        engine._persist_items(items, "src-1", "run-1", topic_id="t1",
                              keywords=keywords)

        # Should add because "tariff" matches
        assert mock_db.add.call_count >= 1

    def test_requires_at_least_2_keywords_for_3plus_keywords(self):
        """When there are 3+ keywords, at least 2 must match."""
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        # Only 1 of 3 keywords matches
        items = [
            FetchItem(title="Tariff update", content="just tariff", url="http://a.com"),
        ]
        keywords = ["tariff", "trade-war", "sanctions"]

        engine._persist_items(items, "src-1", "run-1", topic_id="t1",
                              keywords=keywords)

        # Should NOT add because only 1 keyword matches (need >=2)
        mock_db.add.assert_not_called()

    def test_discards_blank_or_noisy_items(self):
        """Blank or template-like noisy items should be discarded before insert."""
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        items = [
            FetchItem(title="   ", content="首页 | 登录 | 版权 © --", url="http://a.com"),
        ]

        engine._persist_items(items, "src-1", "run-1", topic_id="t1")

        mock_db.add.assert_not_called()

    def test_persists_structured_content_analysis(self):
        """Meaningful items should persist normalized text plus structured metadata."""
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        items = [
            FetchItem(
                title="USTR updates China tariff exclusions",
                content=(
                    "The United States Trade Representative announced China tariff "
                    "exclusion updates affecting lithium battery imports in 2026."
                ),
                url="http://a.com",
                raw_metadata={"engine": "test"},
            ),
        ]

        engine._persist_items(items, "src-1", "run-1", topic_id="t1")

        added = next(
            call.args[0] for call in mock_db.add.call_args_list
            if isinstance(call.args[0], CollectedItem)
        )
        assert added.content == items[0].content
        assert added.summary
        assert added.raw_metadata["engine"] == "test"
        assert added.raw_metadata["content_analysis"]["word_count"] >= 10
        assert added.entities["countries"]

    def test_dedup_skips_existing_items(self):
        """Existing items should be updated, not duplicated."""
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)

        fi = FetchItem(title="News", content="body", url="http://a.com")
        item_id = fi.item_id("src-1")

        # Simulate existing item
        existing = MagicMock(spec=CollectedItem)
        existing.content = "old body"
        existing.topic_id = None
        mock_db.query.return_value.filter.return_value.first.return_value = existing

        engine._persist_items([fi], "src-1", "run-1", topic_id="t1")

        # Should update existing, not add new
        mock_db.add.assert_not_called()
        assert existing.content == "body"  # updated
        assert existing.topic_id == "t1"  # backfilled

    def test_dedup_skips_same_article_from_another_source(self):
        """A canonical URL should prevent duplicate rows across sources and runs."""
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)
        existing = MagicMock(spec=CollectedItem)
        existing.content = "body"
        existing.summary = None
        existing.published_at = None
        existing.topic_id = "t1"
        mock_db.query.return_value.filter.return_value.first.side_effect = [None, existing]

        fi = FetchItem(title="Shared news", content="body", url="https://example.com/article?utm_source=test")
        engine._persist_items([fi], "src-2", "run-2", topic_id="t1")

        mock_db.add.assert_not_called()

    def test_existing_item_receives_newer_curated_profile_fields(self):
        """A better LLM curation pass must refresh searchable editorial fields."""
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)
        existing = MagicMock(spec=CollectedItem)
        existing.title = "Original title"
        existing.content = "old body"
        existing.summary = "old summary"
        existing.language = "en"
        existing.category = "general"
        existing.quality_score = 0.4
        existing.relevance_score = 0.5
        existing.published_at = None
        existing.topic_id = "t1"
        existing.entities = {"countries": ["US"]}
        existing.raw_metadata = {}
        mock_db.query.return_value.filter.return_value.first.return_value = existing
        item = FetchItem(
            title="美国更新关键矿产出口管制",
            content="中" * 240,
            summary="新的中文摘要",
            url="https://example.com/control",
            language="zh",
            category="出口管制",
            quality_score=0.92,
            relevance_score=0.88,
            entities={"products": ["关键矿产"]},
            raw_metadata={"intelligence_profile": {"priority": "high"}},
        )

        engine._persist_items([item], "source-1", "run-1", topic_id="t1")

        assert existing.title == item.title
        assert existing.language == "zh"
        assert existing.category == "出口管制"
        assert existing.quality_score == 0.92
        assert existing.relevance_score == 0.88


def test_topic_source_resolution_uses_only_formal_llm_approved_sources():
    db = MagicMock()
    approved = _allow_full_collection(MagicMock())
    approved.id = "approved"
    approved.channel = SourceChannel.WEB_SCRAPE
    legacy = MagicMock()
    legacy.id = "legacy"
    legacy.channel = SourceChannel.WEB_SCRAPE
    legacy.is_active = True
    legacy.is_configured = True
    legacy.verification_status = "legacy_unverified"
    legacy.robots_status = "unverified"
    legacy.terms_status = "unverified"
    legacy.llm_ingest_allowed = False
    blocked = _allow_full_collection(MagicMock())
    blocked.id = "blocked"
    blocked.channel = SourceChannel.WEB_SCRAPE
    blocked.robots_status = "denied_all"
    db.query.return_value.filter.return_value.all.return_value = [
        approved, legacy, blocked,
    ]
    topic = MagicMock(spec=Topic)
    topic.source_ids = ["approved", "legacy", "blocked"]
    topic.collection_model_ids = None

    sources = CollectionEngine(db)._resolve_sources(topic)

    assert [source.id for source in sources] == ["approved"]


class TestWindowFiltering:
    """Window-based filtering of items by publication date."""

    def test_items_without_published_at_are_skipped_when_window_is_set(self):
        """Items without a usable date should be skipped when a window is set."""
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        items = [
            FetchItem(title="News", content="body", url="http://a.com", published_at=None),
        ]

        window_start = utc_now() - timedelta(days=7)
        engine._persist_items(items, "src-1", "run-1", topic_id="t1",
                              window_start=window_start)

        mock_db.add.assert_not_called()

    def test_items_within_window_kept(self):
        """Items published within the window should be kept."""
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        recent = utc_now() - timedelta(hours=1)
        items = [
            FetchItem(title="Recent news", content="body", url="http://a.com",
                      published_at=recent),
        ]

        window_start = utc_now() - timedelta(days=7)
        engine._persist_items(items, "src-1", "run-1", topic_id="t1",
                              window_start=window_start)

        assert mock_db.add.call_count >= 1

    @patch("app.content_quality.curate_article_candidates", new_callable=AsyncMock)
    @patch("app.connectors.base.ConnectorRegistry.create")
    def test_collection_uses_source_candidate_budget_before_model_review(self, mock_create, mock_curate):
        """The configured source budget should replace the legacy nine-item cap."""
        mock_db = MagicMock()
        source = MagicMock()
        source.id = "source-1"
        source.name = "Source"
        source.is_active = True
        source.max_items_per_run = 12
        _allow_full_collection(source)
        mock_db.query.return_value.filter.return_value.first.return_value = source
        mock_db.query.return_value.filter.return_value.all.return_value = []
        connector = MagicMock()
        connector.execute = AsyncMock(return_value=CollectResult(
            run_id="connector-run", source_id="source-1", status=JobStatus.COMPLETED,
            items=[FetchItem(title=f"Article {index}", content="x" * 250, url=f"https://example.com/{index}", published_at=utc_now()) for index in range(source.max_items_per_run + 4)],
        ))
        mock_create.return_value = connector
        mock_curate.return_value = ([], [])
        engine = CollectionEngine(mock_db)

        import asyncio
        asyncio.run(engine.collect_from_source("source-1", ["Article"], "topic-1"))

        reviewed = mock_curate.call_args.args[0]
        assert len(reviewed) == source.max_items_per_run

    @patch("app.engine.ConnectorRegistry.create")
    def test_collection_policy_blocks_denied_source_before_network(self, mock_create):
        mock_db = MagicMock()
        source = MagicMock()
        source.id = "blocked-source"
        source.name = "Blocked"
        source.is_active = True
        source.is_configured = True
        source.verification_status = "verified"
        source.robots_status = "denied_all"
        source.terms_status = "allowed"
        source.llm_ingest_allowed = True
        mock_db.query.return_value.filter.return_value.first.return_value = source

        import asyncio
        result = asyncio.run(CollectionEngine(mock_db).collect_from_source(
            source.id, ["trade"], "topic-1",
        ))

        assert result.status == JobStatus.FAILED
        assert "robots" in result.error_log[0]
        mock_create.assert_not_called()

    @patch("app.content_quality.curate_article_candidates", new_callable=AsyncMock)
    @patch("app.engine.ConnectorRegistry.create")
    def test_unverified_source_never_sends_excerpt_to_llm(self, mock_create, mock_curate):
        mock_db = MagicMock()
        source = MagicMock()
        source.id = "legacy-source"
        source.name = "Legacy"
        source.is_active = True
        source.is_configured = True
        source.verification_status = "legacy_unverified"
        source.robots_status = "unverified"
        source.terms_status = "unverified"
        source.llm_ingest_allowed = True
        source.max_items_per_run = 10
        mock_db.query.return_value.filter.return_value.first.return_value = source
        connector = MagicMock()
        connector.execute = AsyncMock(return_value=CollectResult(
            run_id="connector-run", source_id=source.id, status=JobStatus.COMPLETED,
            items=[FetchItem(
                title="Trade policy", content="x" * 250,
                url="https://example.com/policy", published_at=utc_now(),
            )],
        ))
        mock_create.return_value = connector

        import asyncio
        result = asyncio.run(CollectionEngine(mock_db).collect_from_source(
            source.id, ["trade"], "topic-1",
        ))

        assert result.status == JobStatus.FAILED
        assert "LLM" in result.error_log[-1]
        mock_create.assert_not_called()
        mock_curate.assert_not_called()

    def test_undated_search_result_is_rejected_even_when_source_requests_bypass(self):
        """A topic window is a hard boundary and cannot be bypassed by a connector."""
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        item = FetchItem(
            title="Undated search result", content="critical minerals update",
            url="https://example.com/article",
            raw_metadata={"engine": "tavily", "allow_undated_results": True},
        )
        engine._persist_items(
            [item], "tavily-search", "run-1", topic_id="t1",
            window_start=utc_now() - timedelta(days=7),
        )

        mock_db.add.assert_not_called()

    def test_search_connector_cannot_bypass_topic_review(self):
        """Connector metadata is untrusted until the shared topic review approves it."""
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        item = FetchItem(
            title="Result selected by search query", content="source excerpt",
            url="https://example.com/article",
            raw_metadata={"engine": "tavily", "allow_unfiltered_results": True},
        )
        engine._persist_items(
            [item], "tavily-search", "run-1", topic_id="t1",
            keywords=["critical minerals", "export control", "rare earth"],
        )

        mock_db.add.assert_not_called()

    def test_search_result_kept_after_shared_topic_review_approves_it(self):
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)
        mock_db.query.return_value.filter.return_value.first.return_value = None

        item = FetchItem(
            title="Semantically reviewed result", content="source excerpt" * 20,
            url="https://example.com/reviewed",
            raw_metadata={
                "engine": "tavily",
                "quality_review": {"topic_relevance_score": 82},
            },
        )
        engine._persist_items(
            [item], "tavily-search", "run-1", topic_id="t1",
            keywords=["critical minerals", "export control", "rare earth"],
        )

        assert mock_db.add.call_count >= 1

    def test_items_before_window_are_skipped_even_when_relevant(self):
        """Relevant items outside the requested window should be skipped."""
        mock_db = MagicMock()
        engine = CollectionEngine(mock_db)
        mock_db.query.return_value.filter.return_value.first.return_value = None
        engine.ensure_tag = MagicMock()
        engine.tag_item = MagicMock(return_value=True)

        old_date = utc_now() - timedelta(days=30)
        items = [
            FetchItem(title="Old tariff news", content="trade tariff policy update", url="http://a.com",
                      published_at=old_date),
        ]

        window_start = utc_now() - timedelta(days=7)
        engine._persist_items(items, "src-1", "run-1", topic_id="t1",
                              window_start=window_start, keywords=["tariff"])

        mock_db.add.assert_not_called()
        engine.ensure_tag.assert_not_called()
        engine.tag_item.assert_not_called()
