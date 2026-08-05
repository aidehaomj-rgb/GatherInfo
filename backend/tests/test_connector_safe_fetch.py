"""SSRF-safe connector boundary tests."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace

from app.connectors.rss_collector import RSSCollector
from app.connectors.json_api import JsonApiCollector
from app.connectors.web_scrape import WebScrapeCollector, _same_origin
from app.models import JobStatus


class _Client:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


def _config(channel: str):
    return SimpleNamespace(
        id=f"{channel}-source",
        base_url="http://127.0.0.1/internal",
        api_endpoint=None,
        auth_config={},
        timeout_seconds=5,
        rate_limit_rps=1,
    )


def test_web_scrape_rejects_url_that_fails_public_html_validation(monkeypatch):
    async def reject(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.connectors.web_scrape.fetch_public_html", reject)
    monkeypatch.setattr(
        "app.connectors.web_scrape.public_async_client", lambda **_kwargs: _Client(),
    )

    result = asyncio.run(WebScrapeCollector(_config("web")).fetch([]))

    assert result.status == JobStatus.FAILED
    assert "非公网" in result.error_log[0]


def test_rss_rejects_url_that_fails_public_xml_validation(monkeypatch):
    async def reject(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.connectors.rss_collector.fetch_public_html", reject)
    monkeypatch.setattr(
        "app.connectors.rss_collector.public_async_client", lambda **_kwargs: _Client(),
    )

    result = asyncio.run(RSSCollector(_config("rss")).fetch([]))

    assert result.status == JobStatus.FAILED
    assert "非公网" in result.error_log[0]


def test_web_detail_hydration_requires_exact_https_origin():
    assert _same_origin(
        "https://customs.example/news", "https://customs.example/detail/1",
    ) is True
    assert _same_origin(
        "https://customs.example/news", "https://cdn.customs.example/detail/1",
    ) is False


def test_json_api_never_sends_configured_credentials_over_http(monkeypatch):
    config = SimpleNamespace(
        id="json-source", base_url="http://api.example.test/data",
        api_endpoint=None, api_key="secret", auth_config={"auth": "bearer"},
        timeout_seconds=5, rate_limit_rps=1, crawl_delay_seconds=0,
        default_keywords=[],
    )
    called = False

    async def should_not_fetch(*_args, **_kwargs):
        nonlocal called
        called = True
        return None

    monkeypatch.setattr("app.connectors.json_api.fetch_public_json", should_not_fetch)

    result = asyncio.run(JsonApiCollector(config).fetch(["trade"]))

    assert result.status == JobStatus.FAILED
    assert "HTTPS" in result.error_log[0]
    assert called is False
    assert _same_origin(
        "https://customs.example/news", "http://customs.example/detail/1",
    ) is False


def test_json_api_maps_collection_window_to_configured_date_parameters():
    config = SimpleNamespace(
        id="federal-register", base_url="https://www.federalregister.gov/api/v1/",
        api_endpoint="documents.json", api_key=None,
        auth_config={
            "auth": "none",
            "query": {"order": "newest"},
            "window_start_param": "conditions[publication_date][gte]",
            "window_end_param": "conditions[publication_date][lte]",
        },
        timeout_seconds=5, rate_limit_rps=1, crawl_delay_seconds=0,
        default_keywords=[],
    )
    collector = JsonApiCollector(config)
    collector.set_collection_window(
        datetime(2026, 8, 2, 16, tzinfo=timezone.utc),
        datetime(2026, 8, 4, 12, tzinfo=timezone.utc),
    )

    params, _, _ = collector._build_request(["tariff"])

    assert params["conditions[publication_date][gte]"] == "2026-08-02"
    assert params["conditions[publication_date][lte]"] == "2026-08-04"


def test_json_api_can_prefer_source_terms_over_multilingual_topic_keywords():
    config = SimpleNamespace(
        id="federal-register", base_url="https://www.federalregister.gov/api/v1/",
        api_endpoint="documents.json", api_key=None,
        auth_config={"auth": "none", "prefer_default_keywords": True},
        timeout_seconds=5, rate_limit_rps=1, crawl_delay_seconds=0,
        default_keywords=["tariff", "customs", "import", "export control"],
    )
    collector = JsonApiCollector(config)

    assert collector._query_terms(["关税", "贸易政策", "RCEP"]) == [
        "tariff", "customs", "import", "export control",
    ]
