"""RSS 1.0/2.0/Atom compatibility and multilingual filtering contracts."""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from xml.etree import ElementTree as ET

from app.connectors.base import FetchItem
from app.connectors.rss_collector import RSSCollector, _filter_by_keywords, _parse_feed
from app.safe_fetch import SafeFetchResult, SafeJsonResult


class _Client:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


def test_parse_rdf_rss_1_item_with_dc_date_and_content() -> None:
    root = ET.fromstring("""<?xml version="1.0"?>
    <rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#"
      xmlns="http://purl.org/rss/1.0/"
      xmlns:dc="http://purl.org/dc/elements/1.1/"
      xmlns:content="http://purl.org/rss/1.0/modules/content/">
      <channel rdf:about="https://example.gov/feed"><title>Notícias</title></channel>
      <item rdf:about="https://example.gov/noticia/1">
        <title>Receita atualiza despacho aduaneiro</title>
        <link>https://example.gov/noticia/1</link>
        <description>Resumo oficial da medida aduaneira.</description>
        <content:encoded><![CDATA[Texto completo sobre importação e fiscalização aduaneira.]]></content:encoded>
        <dc:date>2026-08-03T12:30:00Z</dc:date>
        <dc:type>Notícia</dc:type>
      </item>
    </rdf:RDF>""")

    items = _parse_feed(root, fallback_language="pt")

    assert len(items) == 1
    assert items[0].title == "Receita atualiza despacho aduaneiro"
    assert items[0].content == "Texto completo sobre importação e fiscalização aduaneira."
    assert items[0].published_at == "2026-08-03T12:30:00Z"
    assert items[0].category == "Notícia"
    assert items[0].language == "pt"
    assert items[0].raw_metadata["feed_type"] == "rss1"


def test_explicit_multilingual_semantic_filter_defers_keyword_match_to_llm() -> None:
    items = [FetchItem(
        title="Receita atualiza despacho aduaneiro",
        content="Medida para importação e fiscalização.",
        language="pt",
    )]

    # RSS feeds are topically curated by the publisher, so the connector no
    # longer applies literal keyword filtering — all items pass through to
    # the downstream engine's keyword filter + LLM review for relevance.
    exact = _filter_by_keywords(items, ["关税", "trade policy"])
    semantic = _filter_by_keywords(
        items, ["关税", "trade policy"], defer_to_llm=True,
    )

    assert exact == items
    assert semantic == items


def test_verified_rss_can_hydrate_in_window_same_origin_article(monkeypatch) -> None:
    feed = """<?xml version="1.0"?><rss version="2.0"><channel>
      <item><title>EU customs measure</title>
        <link>https://ec.europa.eu/commission/presscorner/detail/en/ip_26_1</link>
        <description>Short feed excerpt.</description>
        <pubDate>Mon, 03 Aug 2026 09:00:00 GMT</pubDate></item>
      <item><title>Old measure</title>
        <link>https://ec.europa.eu/commission/presscorner/detail/en/ip_26_old</link>
        <description>Old excerpt.</description>
        <pubDate>Fri, 31 Jul 2026 09:00:00 GMT</pubDate></item>
      <item><title>Foreign host</title>
        <link>https://example.com/commission/presscorner/detail/en/unsafe</link>
        <description>Foreign excerpt.</description>
        <pubDate>Mon, 03 Aug 2026 10:00:00 GMT</pubDate></item>
    </channel></rss>"""
    fetched_urls: list[str] = []

    async def fetch(_client, url, **_kwargs):
        fetched_urls.append(url)
        if "api/rss" in url:
            return SafeFetchResult(url, feed, "application/rss+xml", 200)
        html = """<html><body><article><h1>EU customs measure</h1>
          <p>The Commission adopted a customs measure applying from 3 August.</p>
          <p>Importers must provide the new declaration data to customs authorities.</p>
          <p>This official decision sets the affected operators and implementation date.</p>
        </article></body></html>"""
        return SafeFetchResult(url, html, "text/html", 200)

    config = SimpleNamespace(
        id="eu-daily-news-rss", base_url=(
            "https://ec.europa.eu/commission/presscorner/api/rss?language=en"
        ), api_endpoint=None, timeout_seconds=5, rate_limit_rps=10,
        crawl_delay_seconds=0, languages=["en"],
        auth_config={
            "defer_keyword_filter_to_llm": True,
            "follow_item_links": True,
            "item_path_prefixes": ["/commission/presscorner/detail/"],
            "max_detail_items": 4,
        },
    )
    monkeypatch.setattr("app.connectors.rss_collector.fetch_public_html", fetch)
    monkeypatch.setattr(
        "app.connectors.rss_collector.public_async_client", lambda **_kwargs: _Client(),
    )
    collector = RSSCollector(config)
    collector.set_collection_window(
        datetime(2026, 8, 2, 16, tzinfo=timezone.utc),
        datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    result = asyncio.run(collector.fetch(["customs"], max_items=10))

    assert fetched_urls == [
        config.base_url,
        "https://ec.europa.eu/commission/presscorner/detail/en/ip_26_1",
    ]
    assert "Importers must provide" in (result.items[0].content or "")
    assert result.items[0].raw_metadata["detail_hydrated"] is True
    assert result.items[1].content == "Old excerpt."
    assert result.items[2].content == "Foreign excerpt."


def test_eu_presscorner_rss_hydrates_from_official_documents_api(monkeypatch) -> None:
    feed = """<?xml version="1.0"?><rss version="2.0"><channel><item>
      <title>EU trade decision</title>
      <link>https://ec.europa.eu/commission/presscorner/detail/en/ip_26_1707</link>
      <description>Short feed excerpt.</description>
      <pubDate>Mon, 03 Aug 2026 09:00:00 GMT</pubDate>
    </item></channel></rss>"""
    api_calls: list[tuple[str, dict]] = []

    async def fetch_html(_client, url, **_kwargs):
        assert "api/rss" in url
        return SafeFetchResult(url, feed, "application/rss+xml", 200)

    async def fetch_json(_client, url, **kwargs):
        api_calls.append((url, kwargs["params"]))
        return SafeJsonResult(url, {
            "docuLanguageResource": {
                "htmlContent": """<p>The Commission opened a formal trade investigation.</p>
                <p>The measure concerns foreign subsidies affecting EU import competition.</p>
                <p>Companies must preserve evidence and respond before the stated deadline.</p>""",
            },
        }, 200)

    config = SimpleNamespace(
        id="eu-daily-news-rss", base_url=(
            "https://ec.europa.eu/commission/presscorner/api/rss?language=en"
        ), api_endpoint=None, timeout_seconds=5, rate_limit_rps=10,
        crawl_delay_seconds=0, languages=["en"],
        auth_config={
            "defer_keyword_filter_to_llm": True,
            "follow_item_links": True,
            "item_path_prefixes": ["/commission/presscorner/detail/"],
            "detail_fetch_strategy": "eu_presscorner_api",
            "detail_api_endpoint": (
                "https://ec.europa.eu/commission/presscorner/api/documents"
            ),
            "max_detail_items": 4,
        },
    )
    monkeypatch.setattr("app.connectors.rss_collector.fetch_public_html", fetch_html)
    monkeypatch.setattr("app.connectors.rss_collector.fetch_public_json", fetch_json)
    monkeypatch.setattr(
        "app.connectors.rss_collector.public_async_client", lambda **_kwargs: _Client(),
    )
    collector = RSSCollector(config)
    collector.set_collection_window(
        datetime(2026, 8, 2, 16, tzinfo=timezone.utc),
        datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    result = asyncio.run(collector.fetch([], max_items=10))

    assert api_calls == [(
        "https://ec.europa.eu/commission/presscorner/api/documents",
        {"reference": "IP/26/1707", "language": "en"},
    )]
    assert "formal trade investigation" in (result.items[0].content or "")
    assert result.items[0].raw_metadata["detail_strategy"] == "eu_presscorner_api"


def test_eu_daily_news_api_expands_independent_announcements(monkeypatch) -> None:
    feed = """<?xml version="1.0"?><rss version="2.0"><channel><item>
      <title>Daily News 03 / 08 / 2026</title>
      <link>https://ec.europa.eu/commission/presscorner/detail/en/mex_26_1717</link>
      <description>Short roundup excerpt.</description>
      <pubDate>Mon, 03 Aug 2026 09:00:00 GMT</pubDate>
    </item></channel></rss>"""

    async def fetch_html(_client, url, **_kwargs):
        return SafeFetchResult(url, feed, "application/rss+xml", 200)

    async def fetch_json(_client, url, **_kwargs):
        return SafeJsonResult(url, {
            "docutypeResource": {"code": "MEX"},
            "docuLanguageResource": {"htmlContent": """
              <p><strong><u>Commission opens trade investigation</u></strong></p>
              <p>The Commission opened a formal investigation into subsidised imports.</p>
              <p>The measure covers named operators and requires evidence by 20 August.</p>
              <p><strong><u>Commission changes customs declarations</u></strong></p>
              <p>The Commission adopted new customs declaration data requirements.</p>
              <p>Importers must apply them from 3 August at all named entry points.</p>
            """},
        }, 200)

    config = SimpleNamespace(
        id="eu-daily-news-rss", base_url=(
            "https://ec.europa.eu/commission/presscorner/api/rss?language=en"
        ), api_endpoint=None, timeout_seconds=5, rate_limit_rps=10,
        crawl_delay_seconds=0, languages=["en"],
        auth_config={
            "defer_keyword_filter_to_llm": True,
            "follow_item_links": True,
            "item_path_prefixes": ["/commission/presscorner/detail/"],
            "detail_fetch_strategy": "eu_presscorner_api",
            "detail_api_endpoint": (
                "https://ec.europa.eu/commission/presscorner/api/documents"
            ),
            "max_detail_items": 4,
        },
    )
    monkeypatch.setattr("app.connectors.rss_collector.fetch_public_html", fetch_html)
    monkeypatch.setattr("app.connectors.rss_collector.fetch_public_json", fetch_json)
    monkeypatch.setattr(
        "app.connectors.rss_collector.public_async_client", lambda **_kwargs: _Client(),
    )
    collector = RSSCollector(config)
    collector.set_collection_window(
        datetime(2026, 8, 2, 16, tzinfo=timezone.utc),
        datetime(2026, 8, 4, tzinfo=timezone.utc),
    )

    result = asyncio.run(collector.fetch([], max_items=10))

    assert [item.title for item in result.items] == [
        "Commission opens trade investigation",
        "Commission changes customs declarations",
    ]
    assert len({item.url for item in result.items}) == 2
    assert all("traderadar_section=" in (item.url or "") for item in result.items)
    assert all(
        item.raw_metadata["parent_url"].endswith("mex_26_1717")
        for item in result.items
    )
