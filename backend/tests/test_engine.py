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

from app.engine import CollectionEngine, utc_now, _hash
from app.connectors.base import FetchItem, CollectResult
from app.models import CollectedItem, ItemStatus, JobStatus


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

    def test_undated_search_result_kept_when_source_allows_review(self):
        """Trusted search results may be retained when their date is unavailable."""
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

        assert mock_db.add.call_count >= 1

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
