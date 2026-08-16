"""Tests for connector framework (base.py)."""
import asyncio
import pytest

from app.connectors.base import (
    _content_id,
    FetchItem,
    CollectResult,
    BaseCollector,
    ConnectorRegistry,
    register_collector,
)
from app.models import JobStatus, SourceConfig
from app.connectors.broad_web_search import (
    _query_context,
    _relevant_result,
    _unwrap_duckduckgo_url,
    _unwrap_yahoo_url,
)


@pytest.fixture(autouse=True)
def isolate_connector_registry():
    """Keep registry-focused tests from leaking temporary collectors to API tests."""
    original = ConnectorRegistry._collectors
    ConnectorRegistry._collectors = {**original}
    yield
    ConnectorRegistry._collectors = original


def _run_async(coro):
    return asyncio.run(coro)


class TestContentId:
    """content_id should be deterministic: SHA-256 of source|title|url, 16 hex chars."""

    def test_same_input_produces_same_output(self):
        a = _content_id("src1", "Hello World", "https://example.com/1")
        b = _content_id("src1", "Hello World", "https://example.com/1")
        assert a == b
        assert len(a) == 16

    def test_different_title_produces_different_id(self):
        a = _content_id("src1", "Title A", "https://example.com")
        b = _content_id("src1", "Title B", "https://example.com")
        assert a != b

    def test_none_url_is_handled(self):
        result = _content_id("src1", "Title", None)
        assert len(result) == 16

    def test_empty_url_is_handled(self):
        result = _content_id("src1", "Title", "")
        assert len(result) == 16


class TestFetchItem:
    def test_item_id_calls_content_id(self):
        item = FetchItem(title="Test", url="https://x.com")
        cid = item.item_id("src-abc")
        assert len(cid) == 16
        assert cid == _content_id("src-abc", "Test", "https://x.com")

    def test_defaults(self):
        item = FetchItem(title="T")
        assert item.content is None
        assert item.url is None
        assert item.quality_score == 0.0
        assert item.suggested_tags == []


class TestPublicSearchFiltering:
    def test_locale_prefix_is_kept_out_of_query_text(self):
        assert _query_context('ja-JP||"川崎重工業" 中国から輸入') == (
            '"川崎重工業" 中国から輸入', "ja-JP",
        )

    def test_unrelated_regional_search_pollution_is_rejected(self):
        assert not _relevant_result(
            "法医秦明电视剧全集免费在线观看",
            '"Ultralife Corporation" "ABLE New Energy" shipment',
        )
        assert _relevant_result(
            "Ultralife Corporation imports from Able New Energy based in China",
            '"Ultralife Corporation" "ABLE New Energy" shipment',
        )

    def test_duckduckgo_redirect_is_unwrapped(self):
        value = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.importgenius.com%2Fimporters%2Fultralife-corporation"
        assert _unwrap_duckduckgo_url(value) == "https://www.importgenius.com/importers/ultralife-corporation"

    def test_yahoo_redirect_is_unwrapped(self):
        value = (
            "https://r.search.yahoo.com/_ylt=test/RU=https%3a%2f%2finvestor."
            "ultralifecorporation.com%2fnews%2farmy-contract/RK=2/RS=test"
        )
        assert _unwrap_yahoo_url(value) == (
            "https://investor.ultralifecorporation.com/news/army-contract"
        )


class TestCollectResult:
    def test_creation(self):
        r = CollectResult(
            run_id="r1", source_id="s1",
            status=JobStatus.COMPLETED, items=[],
            items_new=5, duration_ms=1200,
        )
        assert r.run_id == "r1"
        assert r.items_new == 5
        assert r.duration_ms == 1200
        assert r.error_log is None


class TestConnectorRegistry:
    def setup_method(self):
        self._original_collectors = {**ConnectorRegistry._collectors}
        ConnectorRegistry._collectors = {}

    def teardown_method(self):
        ConnectorRegistry._collectors = {**self._original_collectors}

    def test_register_and_get(self):
        @register_collector("test_channel")
        class TestCollector(BaseCollector):
            channel = "test_channel"
            async def fetch(self, keywords, max_items=100):
                return CollectResult(run_id="r", source_id="s", status=JobStatus.COMPLETED, items=[])

        assert ConnectorRegistry.get("test_channel") is TestCollector

    def test_get_nonexistent_returns_none(self):
        assert ConnectorRegistry.get("nonexistent") is None

    def test_available_channels(self):
        @register_collector("ch_a")
        class A(BaseCollector):
            channel = "ch_a"
            async def fetch(self, keywords, max_items=100):
                return CollectResult(run_id="r", source_id="s", status=JobStatus.COMPLETED, items=[])

        @register_collector("ch_b")
        class B(BaseCollector):
            channel = "ch_b"
            async def fetch(self, keywords, max_items=100):
                return CollectResult(run_id="r", source_id="s", status=JobStatus.COMPLETED, items=[])

        channels = ConnectorRegistry.available_channels()
        assert "ch_a" in channels
        assert "ch_b" in channels

    def test_create_raises_for_unknown_channel(self):
        from unittest.mock import Mock
        config = Mock(spec=SourceConfig)
        config.channel = "nonexistent"
        with pytest.raises(ValueError, match="No collector"):
            ConnectorRegistry.create(config)

    def test_create_returns_instance(self):
        from unittest.mock import Mock

        @register_collector("my_ch")
        class MyCollector(BaseCollector):
            channel = "my_ch"
            async def fetch(self, keywords, max_items=100):
                return CollectResult(run_id="r", source_id="s", status=JobStatus.COMPLETED, items=[])

        config = Mock(spec=SourceConfig)
        config.channel = "my_ch"
        collector = ConnectorRegistry.create(config)
        assert isinstance(collector, MyCollector)
        assert collector.config is config

    def test_create_from_enum_channel(self):
        from unittest.mock import Mock
        from app.models import SourceChannel

        @register_collector("rss")
        class RSSCollector(BaseCollector):
            channel = "rss"
            async def fetch(self, keywords, max_items=100):
                return CollectResult(run_id="r", source_id="s", status=JobStatus.COMPLETED, items=[])

        config = Mock(spec=SourceConfig)
        config.channel = SourceChannel.RSS
        collector = ConnectorRegistry.create(config)
        assert isinstance(collector, RSSCollector)


class TestBaseCollectorExecute:
    """Test the execute() lifecycle using asyncio.run()."""

    def setup_method(self):
        self._original_collectors = {**ConnectorRegistry._collectors}
        ConnectorRegistry._collectors = {}

    def teardown_method(self):
        ConnectorRegistry._collectors = {**self._original_collectors}

    def test_execute_happy_path(self):
        @register_collector("happy")
        class HappyCollector(BaseCollector):
            channel = "happy"
            async def fetch(self, keywords, max_items=100):
                return CollectResult(
                    run_id="r-x", source_id="s-x",
                    status=JobStatus.COMPLETED,
                    items=[FetchItem(title="Item 1"), FetchItem(title="Item 2")],
                    items_new=2, duration_ms=500,
                )

        from unittest.mock import Mock
        config = Mock(spec=SourceConfig)
        config.max_items_per_run = 100
        collector = HappyCollector(config)

        run = Mock()
        run.id = "run-test"
        run.source_id = "src-test"

        result = _run_async(collector.execute(run, ["kw1", "kw2"]))

        assert result.status == JobStatus.COMPLETED
        assert result.items_new == 2
        assert len(result.items) == 2
        assert run.status == JobStatus.COMPLETED
        assert run.items_found == 2
        assert run.completed_at is not None

    def test_execute_error_path(self):
        @register_collector("sad")
        class SadCollector(BaseCollector):
            channel = "sad"
            async def fetch(self, keywords, max_items=100):
                raise RuntimeError("Connection refused")

        from unittest.mock import Mock
        config = Mock(spec=SourceConfig)
        config.max_items_per_run = 100
        collector = SadCollector(config)

        run = Mock()
        run.id = "run-fail"
        run.source_id = "src-fail"

        result = _run_async(collector.execute(run, ["kw"]))

        assert result.status == JobStatus.FAILED
        assert result.items == []
        assert "Connection refused" in result.error_log[0]
        assert run.status == JobStatus.FAILED
        assert "Connection refused" in run.error_log[0]
