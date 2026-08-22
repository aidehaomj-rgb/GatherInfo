import asyncio
from types import SimpleNamespace

from app.connectors.web_scrape import WebScrapeCollector
from app.safe_fetch import SafeFetchResult
from app.web_content_extractor import extract_article_text


class _Client:
    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None


def _config():
    return SimpleNamespace(
        id="target-source", name="Target Source",
        base_url="https://example.gov/news", homepage_url="https://example.gov/",
        auth_config={"target_only": True}, timeout_seconds=5,
        rate_limit_rps=1000, crawl_delay_seconds=0, max_items_per_run=20,
    )


def test_explicit_target_url_fetches_article_body_not_workbook_summary(monkeypatch) -> None:
    html = """
    <html><head><meta property="article:published_time" content="2026-08-13" /></head>
    <body><article><h1>India adjusts China tariff</h1>
    <p>India customs announced a tariff adjustment affecting imports from China.</p>
    <p>This second paragraph provides the customs measure, implementation date,
    affected goods, and the complete evidence needed for collection review.</p>
    </article></body></html>
    """

    async def fetch(_client, url, **_kwargs):
        return SafeFetchResult(url=url, text=html, content_type="text/html", status_code=200)

    monkeypatch.setattr("app.connectors.web_scrape.fetch_public_html", fetch)
    monkeypatch.setattr(
        "app.connectors.web_scrape.public_async_client", lambda **_kwargs: _Client(),
    )
    collector = WebScrapeCollector(_config())
    collector.set_target_urls(["https://example.gov/news/tariff-1"])

    result = asyncio.run(collector.fetch(["tariff", "China"], max_items=10))

    assert len(result.items) == 1
    assert result.items[0].url == "https://example.gov/news/tariff-1"
    assert "second paragraph" in result.items[0].content
    assert result.items[0].published_at == "2026-08-13"
    assert result.items[0].raw_metadata["collection_method"] == "explicit_target"


def test_explicit_target_must_match_the_verified_source_origin(monkeypatch) -> None:
    called = False

    async def fetch(*_args, **_kwargs):
        nonlocal called
        called = True
        return None

    monkeypatch.setattr("app.connectors.web_scrape.fetch_public_html", fetch)
    monkeypatch.setattr(
        "app.connectors.web_scrape.public_async_client", lambda **_kwargs: _Client(),
    )
    collector = WebScrapeCollector(_config())
    collector.set_target_urls(["http://example.gov:8080/news/tariff-1"])

    result = asyncio.run(collector.fetch(["tariff"], max_items=10))

    assert result.items == []
    assert called is False


def test_explicit_target_mode_does_not_crawl_source_listing(monkeypatch) -> None:
    fetched_urls: list[str] = []
    html = """
    <html><body><article><h1>Customs risk notice</h1>
    <p>Customs authorities published a cross-border risk notice concerning trade
    compliance controls, affected operators, and the implementation timeline.</p>
    <p>The original notice includes enough independent body text for collection.</p>
    </article></body></html>
    """

    async def fetch(_client, url, **_kwargs):
        fetched_urls.append(url)
        return SafeFetchResult(url=url, text=html, content_type="text/html", status_code=200)

    monkeypatch.setattr("app.connectors.web_scrape.fetch_public_html", fetch)
    monkeypatch.setattr(
        "app.connectors.web_scrape.public_async_client", lambda **_kwargs: _Client(),
    )
    config = _config()
    config.auth_config = {}
    collector = WebScrapeCollector(config)
    collector.set_target_urls(
        ["https://example.gov/news/risk-1"], mode="explicit",
    )

    result = asyncio.run(collector.fetch(["customs", "risk"], max_items=10))

    assert len(result.items) == 1
    assert fetched_urls == ["https://example.gov/news/risk-1"]


def test_article_extractor_reads_json_ld_publication_date_before_noise_removal() -> None:
    html = """
    <html><head><script type="application/ld+json">
    {"@type":"NewsArticle","headline":"Customs notice",
     "datePublished":"2026-07-29T08:49:00-03:00"}
    </script></head><body><article><h1>Customs notice</h1>
    <p>This is a complete customs risk management article with sufficient body.</p>
    </article></body></html>
    """

    result = extract_article_text(html)

    assert result["published_at"] == "2026-07-29T08:49:00-03:00"
