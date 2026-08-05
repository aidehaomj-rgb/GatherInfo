import asyncio
from types import SimpleNamespace

from app.connectors.tavily_search import TavilyCollector


class _Response:
    status_code = 200

    def __init__(self, *, payload=None, text="", error=None):
        self._payload = payload or {"results": []}
        self.text = text
        self._error = error

    def raise_for_status(self):
        if self._error:
            raise self._error
        return None

    def json(self):
        return self._payload


class _Client:
    def __init__(self, payloads, *, results=None, detail_html="", detail_error=None):
        self.payloads = payloads
        self.results = results or []
        self.detail_html = detail_html
        self.detail_error = detail_error
        self.get_calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def post(self, _url, json):
        self.payloads.append(json)
        return _Response(payload={"results": self.results})

    async def get(self, url, **kwargs):
        self.get_calls.append((url, kwargs))
        return _Response(text=self.detail_html, error=self.detail_error)


class _ConcurrentClient(_Client):
    def __init__(self, payloads):
        super().__init__(payloads)
        self.active = 0
        self.max_active = 0

    async def post(self, _url, json):
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        await asyncio.sleep(0.03)
        self.payloads.append(json)
        self.active -= 1
        return _Response(payload={"results": []})


def _patch_http(monkeypatch, client):
    async def fake_fetch_public_html(request_client, url, **kwargs):
        request_client.get_calls.append((url, kwargs))
        if request_client.detail_error:
            raise request_client.detail_error
        return SimpleNamespace(text=request_client.detail_html, url=url)

    monkeypatch.setattr(
        "app.connectors.tavily_search.public_async_client",
        lambda **_kwargs: client,
    )
    monkeypatch.setattr(
        "app.connectors.tavily_search.fetch_public_html",
        fake_fetch_public_html,
    )


def _config(
    *,
    verification_status="verified",
    robots_status="allowed",
    terms_status="public_domain",
    llm_ingest_allowed=True,
    origin_resolution_required=False,
    **auth_config,
):
    return SimpleNamespace(
        auth_config=auth_config,
        api_key="test-key",
        api_key_ref=None,
        default_keywords=["generic source query"],
        timeout_seconds=1,
        rate_limit_rps=100,
        id="tavily-search",
        default_categories=None,
        is_active=True,
        is_configured=True,
        verification_status=verification_status,
        robots_status=robots_status,
        terms_status=terms_status,
        llm_ingest_allowed=llm_ingest_allowed,
        origin_resolution_required=origin_resolution_required,
    )


def test_topic_keywords_override_tavily_source_defaults(monkeypatch):
    payloads = []
    client = _Client(payloads)
    _patch_http(monkeypatch, client)

    collector = TavilyCollector(_config(prefer_default_keywords=True))
    asyncio.run(collector.fetch(["critical minerals export control"], max_items=1))

    assert [payload["query"] for payload in payloads] == [
        "critical minerals export control"
    ]


def test_multiple_tavily_queries_use_bounded_concurrency(monkeypatch):
    client = _ConcurrentClient([])
    _patch_http(monkeypatch, client)

    asyncio.run(TavilyCollector(_config()).fetch(
        ["query one", "query two", "query three", "query four"],
        max_items=40,
    ))

    assert client.max_active == 3
    assert sorted(payload["query"] for payload in client.payloads) == [
        "query four", "query one", "query three", "query two",
    ]


def test_short_snippet_reuses_detail_request_to_hydrate_article_metadata(monkeypatch):
    snippet = "The EU published a short notice about a new battery rule."
    body = (
        "The European Union adopted a detailed battery due-diligence rule for "
        "importers and manufacturers. " * 12
    )
    detail_html = f"""
        <html><head>
          <meta property="article:published_time" content="2026-07-31T08:30:00Z">
        </head><body><article>
          <h1>EU Battery Rule: Full Regulatory Analysis</h1>
          <p>{body}</p>
          <p>Companies must document supply-chain controls and reporting.</p>
        </article></body></html>
    """
    source_url = "https://example.org/eu-battery-rule"
    client = _Client(
        [],
        results=[{
            "title": "EU Battery Rule",
            "content": snippet,
            "url": source_url,
            "score": 0.91,
        }],
        detail_html=detail_html,
    )
    _patch_http(monkeypatch, client)

    item = asyncio.run(
        TavilyCollector(_config(hydrate_search_results=True)).fetch(
            ["battery"], max_items=1
        )
    ).items[0]

    assert item.url == source_url
    assert item.title == "EU Battery Rule: Full Regulatory Analysis"
    assert len(item.content) > len(snippet)
    assert item.summary and len(item.summary) > len(snippet)
    assert item.published_at == "2026-07-31T08:30:00+00:00"
    assert item.language == "en"
    assert len(client.get_calls) == 1
    assert client.get_calls[0][0] == source_url


def test_legacy_source_never_fetches_detail_page_for_hydration(monkeypatch):
    source_url = "https://example.org/unverified"
    client = _Client([], results=[{
        "title": "Unverified result",
        "content": "Short search snippet.",
        "url": source_url,
        "score": 0.8,
    }])
    _patch_http(monkeypatch, client)

    result = asyncio.run(TavilyCollector(_config(
        hydrate_search_results=True,
        verification_status="legacy_unverified",
        robots_status="unverified",
        terms_status="unverified",
    )).fetch(["trade"], max_items=1))

    assert result.items[0].content == "Short search snippet."
    assert client.get_calls == []


def test_origin_resolution_required_skips_unapproved_origin_metadata_request(monkeypatch):
    snippet = "A sufficiently detailed API snippet about trade policy. " * 5
    source_url = "https://example.org/policy"
    client = _Client([], results=[{
        "title": "Trade policy",
        "content": snippet,
        "url": source_url,
        "score": 0.9,
    }], detail_html="""
        <html><head><meta property="article:published_time"
        content="2026-08-03T08:00:00Z"></head><body><article>
        <h1>Different detail title</h1><p>Full page body must not replace API output.</p>
        </article></body></html>
    """)
    _patch_http(monkeypatch, client)

    item = asyncio.run(TavilyCollector(_config(
        hydrate_search_results=True,
        origin_resolution_required=True,
    )).fetch(["trade"], max_items=1)).items[0]

    assert item.published_at is None
    assert item.content == snippet
    assert item.title == "Trade policy"
    assert client.get_calls == []


def test_opt_in_tavily_raw_content_is_used_for_llm_curation(monkeypatch):
    payloads = []
    raw_content = "Complete source article with customs facts. " * 40
    client = _Client(payloads, results=[{
        "title": "Customs policy",
        "content": "Short API snippet.",
        "raw_content": raw_content,
        "url": "https://example.org/customs-policy",
        "published_date": "2026-08-03T08:00:00Z",
        "score": 0.9,
    }])
    _patch_http(monkeypatch, client)

    item = asyncio.run(TavilyCollector(_config(
        include_raw_content=True,
    )).fetch(["customs"], max_items=1)).items[0]

    assert payloads[0]["include_raw_content"] is True
    assert item.content == raw_content
    assert item.summary == "Short API snippet."
    assert item.raw_metadata["content_source"] == "tavily_raw_content"


def test_detail_hydration_keeps_search_title_and_published_date_priority(monkeypatch):
    source_url = "https://example.org/source-article"
    original_title = "Original Search Headline"
    client = _Client(
        [],
        results=[{
            "title": original_title,
            "content": "Short search snippet.",
            "url": source_url,
            "published_date": "2026-08-01T03:00:00Z",
            "score": 0.8,
        }],
        detail_html="""
          <html><head>
            <meta property="article:published_time" content="2026-07-01T00:00:00Z">
          </head><body><article>
            <h1>Unrelated Page Heading</h1>
            <p>This is a substantially fuller article body about global trade controls. """
            + ("It contains verified detail from the source page. " * 16)
            + "</p></article></body></html>",
    )
    _patch_http(monkeypatch, client)

    item = asyncio.run(
        TavilyCollector(_config(hydrate_search_results=True)).fetch(
            ["trade"], max_items=1
        )
    ).items[0]

    assert item.title == original_title
    assert item.published_at == "2026-08-01T03:00:00+00:00"
    assert "verified detail" in item.content
    assert len(client.get_calls) == 1


def test_detail_access_failure_degrades_to_original_search_result(monkeypatch):
    source = {
        "title": "Original headline",
        "content": "Original short snippet.",
        "url": "https://example.org/restricted",
        "score": 0.7,
    }
    client = _Client([], results=[source], detail_error=RuntimeError("403 forbidden"))
    _patch_http(monkeypatch, client)

    item = asyncio.run(
        TavilyCollector(_config(hydrate_search_results=True)).fetch(
            ["trade"], max_items=1
        )
    ).items[0]

    assert item.title == source["title"]
    assert item.content == source["content"]
    assert item.summary == source["content"]
    assert item.url == source["url"]
    assert item.published_at is None
    assert len(client.get_calls) == 1


def test_detail_metadata_does_not_replace_more_complete_search_text(monkeypatch):
    snippet = (
        "The search result already contains a more complete account of the measure, "
        "its affected products, implementation date, and compliance obligations. " * 3
    )
    client = _Client(
        [],
        results=[{
            "title": "Complete Search Headline",
            "content": snippet,
            "url": "https://example.org/thin-page",
            "score": 0.75,
        }],
        detail_html="""
          <html><body><article>
            <h1>Different title</h1>
            <p>A shorter page extract with little additional detail.</p>
          </article></body></html>
        """,
    )
    _patch_http(monkeypatch, client)

    item = asyncio.run(
        TavilyCollector(_config(hydrate_search_results=True)).fetch(
            ["trade"], max_items=1
        )
    ).items[0]

    assert item.title == "Complete Search Headline"
    assert item.content == snippet
    assert item.summary == snippet[:500]
    assert len(client.get_calls) == 1


def test_search_result_hydration_is_opt_in(monkeypatch):
    snippet = "Short search snippet."
    client = _Client(
        [],
        results=[{
            "title": "Search headline",
            "content": snippet,
            "url": "https://example.org/full-article",
            "published_date": "2026-08-01T03:00:00Z",
            "score": 0.8,
        }],
        detail_html="""
          <html><body><article><h1>Search headline with more detail</h1>
          <p>This page has a much longer article body. """
          + ("Additional verified reporting. " * 30)
          + "</p></article></body></html>",
    )
    _patch_http(monkeypatch, client)

    item = asyncio.run(TavilyCollector(_config()).fetch(["trade"], max_items=1)).items[0]

    assert item.content == snippet
    assert item.title == "Search headline"
    assert client.get_calls == []


def test_date_resolution_reuses_metadata_without_default_hydration(monkeypatch):
    snippet = "Short original snippet."
    client = _Client(
        [],
        results=[{
            "title": "Original search title",
            "content": snippet,
            "url": "https://example.org/dated-article",
            "score": 0.82,
        }],
        detail_html="""
          <html><head>
            <meta property="article:published_time" content="2026-07-29T09:15:00Z">
          </head><body><article><h1>Original search title with more detail</h1>
          <p>This page has a much longer article body. """
          + ("Additional verified reporting. " * 30)
          + "</p></article></body></html>",
    )
    _patch_http(monkeypatch, client)

    item = asyncio.run(TavilyCollector(_config()).fetch(["trade"], max_items=1)).items[0]

    assert item.published_at == "2026-07-29T09:15:00+00:00"
    assert item.title == "Original search title"
    assert item.content == snippet
    assert item.summary == snippet
    assert len(client.get_calls) == 1


def test_hydration_can_run_when_page_date_resolution_is_disabled(monkeypatch):
    snippet = "Short original snippet."
    client = _Client(
        [],
        results=[{
            "title": "Original title",
            "content": snippet,
            "url": "https://example.org/article",
            "score": 0.83,
        }],
        detail_html="""
          <html><head>
            <meta property="article:published_time" content="2026-07-29T09:15:00Z">
          </head><body><article><h1>Original title with detail</h1>
          <p>This page has a much longer article body. """
          + ("Additional verified reporting. " * 30)
          + "</p></article></body></html>",
    )
    _patch_http(monkeypatch, client)
    collector = TavilyCollector(_config(
        hydrate_search_results=True,
        resolve_published_dates=False,
    ))

    item = asyncio.run(collector.fetch(["trade"], max_items=1)).items[0]

    assert len(item.content) > len(snippet)
    assert item.published_at is None
    assert len(client.get_calls) == 1
