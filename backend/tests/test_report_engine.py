"""
Tests for report engine — prompt building, ISO parsing, auto-summary, context building.

Run: cd backend && python -m pytest tests/test_report_engine.py -v
"""
import os
import sys
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.report_engine import (
    _parse_iso,
    _build_item_context,
    _build_collection_summary_context,
    _build_report_prompt,
    _auto_summary,
)
from app.models import CollectedItem, Topic


# ── _parse_iso ──────────────────────────────────────────────────────────────

class TestParseIso:
    def test_none_returns_none(self):
        assert _parse_iso(None) is None

    def test_empty_string_returns_none(self):
        assert _parse_iso("") is None

    def test_valid_iso_with_z(self):
        result = _parse_iso("2024-06-15T12:30:00Z")
        assert result is not None
        assert result.tzinfo is not None
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15

    def test_valid_iso_with_offset(self):
        result = _parse_iso("2024-06-15T12:30:00+08:00")
        assert result is not None
        assert result.tzinfo is not None
        assert result.hour == 12

    def test_date_only_string(self):
        result = _parse_iso("2024-06-15")
        assert result is not None
        assert result.tzinfo is not None  # UTC assigned
        assert result.year == 2024
        assert result.month == 6
        assert result.day == 15

    def test_invalid_string_returns_none(self):
        assert _parse_iso("not-a-date") is None

    def test_strips_whitespace(self):
        result = _parse_iso("  2024-06-15T12:30:00Z  ")
        assert result is not None
        assert result.day == 15


# ── _build_item_context ─────────────────────────────────────────────────────

class TestBuildItemContext:
    def test_empty_list_returns_empty(self):
        assert _build_item_context([]) == []

    def test_single_item_conversion(self):
        item = MagicMock(spec=CollectedItem)
        item.id = "item-1"
        item.title = "Test Title"
        item.summary = "Test Summary"
        item.content = "A" * 2500  # > 2000 to test truncation
        item.url = "http://example.com/1"
        item.source_id = "src-1"
        item.language = "en"
        item.category = "trade"
        item.tags = []
        item.published_at = datetime(2024, 6, 15, tzinfo=timezone.utc)
        item.relevance_score = 0.85

        result = _build_item_context([item])

        assert len(result) == 1
        r = result[0]
        assert r["id"] == "item-1"
        assert r["title"] == "Test Title"
        assert r["summary"] == "Test Summary"
        assert len(r["content"]) == 2000  # truncated
        assert r["url"] == "http://example.com/1"
        assert r["source"] == "src-1"
        assert r["language"] == "en"
        assert r["category"] == "trade"
        assert r["tags"] == []
        assert r["published_at"] == "2024-06-15T00:00:00+00:00"
        assert r["relevance_score"] == 0.85

    def test_multiple_items(self):
        items = []
        for i in range(3):
            item = MagicMock(spec=CollectedItem)
            item.id = f"item-{i}"
            item.title = f"Title {i}"
            item.summary = ""
            item.content = ""
            item.url = ""
            item.source_id = "src-1"
            item.language = "zh"
            item.category = "policy"
            item.tags = []
            item.published_at = None
            item.relevance_score = 0.0
            items.append(item)

        result = _build_item_context(items)
        assert len(result) == 3
        assert result[0]["id"] == "item-0"
        assert result[2]["id"] == "item-2"

    def test_tags_conversion(self):
        tag1 = MagicMock()
        tag1.namespace = "region"
        tag1.value = "US"

        tag2 = MagicMock()
        tag2.namespace = "topic"
        tag2.value = "tariff"

        item = MagicMock(spec=CollectedItem)
        item.id = "item-1"
        item.title = "T"
        item.summary = ""
        item.content = ""
        item.url = ""
        item.source_id = "s"
        item.language = "en"
        item.category = "trade"
        item.tags = [tag1, tag2]
        item.published_at = None
        item.relevance_score = 0.0

        result = _build_item_context([item])
        assert len(result[0]["tags"]) == 2
        assert result[0]["tags"][0] == {"namespace": "region", "value": "US"}
        assert result[0]["tags"][1] == {"namespace": "topic", "value": "tariff"}

    def test_none_tags_handled(self):
        item = MagicMock(spec=CollectedItem)
        item.id = "item-1"
        item.title = "T"
        item.summary = ""
        item.content = ""
        item.url = ""
        item.source_id = "s"
        item.language = "en"
        item.category = "trade"
        item.tags = None
        item.published_at = None
        item.relevance_score = 0.0

        result = _build_item_context([item])
        assert result[0]["tags"] == []

    def test_none_summary_handled(self):
        item = MagicMock(spec=CollectedItem)
        item.id = "item-1"
        item.title = "T"
        item.summary = None
        item.content = None
        item.url = None
        item.source_id = "s"
        item.language = None
        item.category = None
        item.tags = []
        item.published_at = None
        item.relevance_score = None

        result = _build_item_context([item])
        assert result[0]["summary"] == ""
        assert result[0]["content"] == ""
        assert result[0]["url"] == ""
        assert result[0]["language"] == "unknown"
        assert result[0]["category"] == "unknown"
        assert result[0]["relevance_score"] == 0.0


# ── _build_report_prompt ────────────────────────────────────────────────────

class TestBuildReportPrompt:
    def _make_topic(self, name="Test Topic", description="Test Desc",
                    keyword_tags=None):
        topic = MagicMock(spec=Topic)
        topic.name = name
        topic.description = description
        topic.keyword_tags = keyword_tags
        return topic

    def _make_item_ctx(self, n=1):
        return [{
            "id": f"item-{i}",
            "title": f"Title {i}",
            "summary": f"Summary {i}",
            "content": f"Content {i}",
            "url": f"http://example.com/{i}",
            "source": "src-1",
            "language": "zh",
            "category": "trade",
            "tags": [],
            "published_at": "",
            "relevance_score": 0.5,
        } for i in range(1, n + 1)]

    def test_prompt_contains_topic_name(self):
        topic = self._make_topic(name="关税分析")
        prompt = _build_report_prompt(topic, self._make_item_ctx(2))
        assert "关税分析" in prompt
        assert "## " in prompt  # markdown headings

    def test_prompt_contains_item_count(self):
        topic = self._make_topic()
        prompt = _build_report_prompt(topic, self._make_item_ctx(5))
        assert "共 5 条" in prompt

    def test_prompt_contains_keyword_tags(self):
        topic = self._make_topic(
            keyword_tags=json.dumps([
                {"keyword": "关税", "weight": 1.0},
                {"keyword": "制裁", "weight": 0.8},
            ])
        )
        prompt = _build_report_prompt(topic, self._make_item_ctx(1))
        assert "关税" in prompt
        assert "制裁" in prompt
        assert "权重" in prompt

    def test_prompt_with_invalid_keyword_tags(self):
        """Malformed JSON in keyword_tags should not crash."""
        topic = self._make_topic(keyword_tags="not valid json{{{")
        prompt = _build_report_prompt(topic, self._make_item_ctx(1))
        assert "Test Topic" in prompt  # still builds fine

    def test_prompt_with_empty_keyword_tags(self):
        topic = self._make_topic(keyword_tags="[]")
        prompt = _build_report_prompt(topic, self._make_item_ctx(1))
        assert "关键词及权重" not in prompt  # empty list → no section

    def test_prompt_without_keyword_tags(self):
        topic = self._make_topic(keyword_tags=None)
        prompt = _build_report_prompt(topic, self._make_item_ctx(1))
        assert "关键词及权重" not in prompt

    def test_prompt_with_date_range(self):
        topic = self._make_topic()
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        end = datetime(2024, 6, 15, tzinfo=timezone.utc)
        prompt = _build_report_prompt(topic, self._make_item_ctx(1), start, end)
        assert "2024-01-01" in prompt
        assert "2024-06-15" in prompt
        assert "数据时间范围" in prompt

    def test_prompt_with_partial_date_range(self):
        topic = self._make_topic()
        start = datetime(2024, 1, 1, tzinfo=timezone.utc)
        prompt = _build_report_prompt(topic, self._make_item_ctx(1), start, None)
        assert "2024-01-01" in prompt
        assert "(不限)" in prompt

    def test_prompt_no_date_range(self):
        topic = self._make_topic()
        prompt = _build_report_prompt(topic, self._make_item_ctx(1))
        assert "数据时间范围" not in prompt

    def test_prompt_contains_required_sections(self):
        topic = self._make_topic()
        prompt = _build_report_prompt(topic, self._make_item_ctx(2))
        assert "执行摘要" in prompt
        assert "关键发现" in prompt
        assert "数据概览" in prompt
        assert "详细分析" in prompt
        assert "趋势研判" in prompt
        assert "建议行动" in prompt

    def test_prompt_contains_item_titles(self):
        topic = self._make_topic()
        items = [{
            "id": "item-1", "title": "Breaking News: Tariffs Raised",
            "summary": "S", "content": "C", "url": "http://x.com",
            "source": "src", "language": "en", "category": "trade",
            "tags": [], "published_at": "", "relevance_score": 0.9,
        }]
        prompt = _build_report_prompt(topic, items)
        assert "Breaking News: Tariffs Raised" in prompt

    def test_prompt_handles_empty_description(self):
        topic = self._make_topic(description=None)
        prompt = _build_report_prompt(topic, self._make_item_ctx(1))
        assert "(无)" in prompt

    def test_collection_summary_context_groups_evidence_before_report(self):
        items = [
            {
                "id": "item-1",
                "index": 1,
                "title": "US tariff exclusion update",
                "summary": "USTR extended tariff exclusions for selected products.",
                "content": "Long body",
                "url": "http://example.com/1",
                "source": "ustr",
                "language": "en",
                "category": "tariff",
                "tags": [{"namespace": "system", "value": "超限采集"}],
                "published_at": "2024-01-01T00:00:00+00:00",
                "relevance_score": 0.9,
            },
            {
                "id": "item-2",
                "index": 2,
                "title": "EU customs guidance",
                "summary": "EU issued new customs compliance guidance.",
                "content": "Long body",
                "url": "http://example.com/2",
                "source": "eu",
                "language": "en",
                "category": "customs",
                "tags": [],
                "published_at": "2024-01-02T00:00:00+00:00",
                "relevance_score": 0.8,
            },
        ]

        result = _build_collection_summary_context(items)

        assert "信息集合摘要" in result
        assert "tariff 1 条" in result
        assert "customs 1 条" in result
        assert "超限采集" in result
        assert "[条目1]" in result

    def test_prompt_requires_summary_then_synthesis(self):
        topic = self._make_topic()
        prompt = _build_report_prompt(topic, self._make_item_ctx(2))

        summary_pos = prompt.index("【信息集合摘要】")
        detail_pos = prompt.index("【详细条目】")
        assert summary_pos < detail_pos
        assert "先基于信息集合摘要形成判断" in prompt


# ── _auto_summary ───────────────────────────────────────────────────────────

class TestAutoSummary:
    def test_short_text_returns_full(self):
        text = "Hello world"
        result = _auto_summary(text)
        assert result == text

    def test_long_text_truncated(self):
        text = "A" * 300
        result = _auto_summary(text)
        assert len(result) == 203  # 200 chars + "..."
        assert result.endswith("...")

    def test_exactly_200_chars(self):
        text = "B" * 200
        result = _auto_summary(text)
        assert len(result) == 200
        assert not result.endswith("...")

    def test_empty_string(self):
        assert _auto_summary("") == ""
