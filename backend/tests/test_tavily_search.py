import asyncio
from types import SimpleNamespace

from app.connectors.tavily_search import TavilyCollector


class _Response:
    status_code = 200

    def raise_for_status(self):
        return None

    def json(self):
        return {"results": []}


class _Client:
    def __init__(self, payloads):
        self.payloads = payloads

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, traceback):
        return None

    async def post(self, _url, json):
        self.payloads.append(json)
        return _Response()


def test_topic_keywords_override_tavily_source_defaults(monkeypatch):
    payloads = []
    config = SimpleNamespace(
        auth_config={"prefer_default_keywords": True},
        api_key="test-key",
        api_key_ref=None,
        default_keywords=["generic source query"],
        timeout_seconds=1,
        rate_limit_rps=100,
        id="tavily-search",
        default_categories=None,
    )

    monkeypatch.setattr(
        "app.connectors.tavily_search.httpx.AsyncClient",
        lambda **_kwargs: _Client(payloads),
    )

    collector = TavilyCollector(config)
    asyncio.run(collector.fetch(["critical minerals export control"], max_items=1))

    assert [payload["query"] for payload in payloads] == ["critical minerals export control"]
