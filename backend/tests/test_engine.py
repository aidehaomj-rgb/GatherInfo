"""
Tests for the collection engine — keyword filtering, dedup, persistence, auto-tagging.

Run: cd backend && python -m pytest tests/test_engine.py -v
"""
import os
import sys
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

# Ensure the backend package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.engine import (
    CollectionEngine, MAX_CANDIDATES_PER_SOURCE,
    SOURCE_EXECUTION_TIMEOUT_SECONDS, utc_now, _hash,
)
from app.connectors.base import FetchItem, CollectResult
from app.models import CollectedItem, CollectionRun, ItemStatus, JobStatus


def test_hash_deterministic():
    """_hash returns the same output for the same input."""
    assert _hash("hello") == _hash("hello")
    assert _hash("hello") != _hash("world")
    assert len(_hash("test")) == 64  # SHA-256 hex


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

        added = mock_db.add.call_args.args[0]
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
    def test_collection_caps_candidates_before_model_review(self, mock_create, mock_curate):
        """A large source response must not create an unbounded LLM review queue."""
        mock_db = MagicMock()
        source = MagicMock()
        source.id = "source-1"
        source.name = "Source"
        source.is_active = True
        source.max_items_per_run = 100
        mock_db.query.return_value.filter.return_value.first.return_value = source
        mock_db.query.return_value.filter.return_value.all.return_value = []
        connector = MagicMock()
        connector.execute = AsyncMock(return_value=CollectResult(
            run_id="connector-run", source_id="source-1", status=JobStatus.COMPLETED,
            items=[FetchItem(title=f"Article {index}", content="x" * 250, url=f"https://example.com/{index}", published_at=utc_now()) for index in range(MAX_CANDIDATES_PER_SOURCE + 4)],
        ))
        mock_create.return_value = connector
        mock_curate.return_value = ([], [])
        engine = CollectionEngine(mock_db)

        import asyncio
        asyncio.run(engine.collect_from_source("source-1", ["Article"], "topic-1"))

        reviewed = mock_curate.call_args.args[0]
        assert len(reviewed) == MAX_CANDIDATES_PER_SOURCE

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

    def test_search_result_kept_when_source_allows_topic_review(self):
        """A search result selected by the topic query may bypass generic matching."""
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
