import asyncio
from pathlib import Path
import sys

import httpx
import httpcore
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.safe_fetch import (
    PublicNetworkBackend, fetch_public_html, fetch_public_json, validate_public_url,
)


class _RecordingBackend:
    def __init__(self):
        self.connected_hosts = []

    async def connect_tcp(self, host, port, **_kwargs):
        self.connected_hosts.append((host, port))
        return object()

    async def connect_unix_socket(self, *_args, **_kwargs):
        raise AssertionError("Unix sockets are not allowed")

    async def sleep(self, _seconds):
        return None


def test_validate_public_url_allows_public_https_address():
    decision = asyncio.run(validate_public_url(
        "https://example.com/news/1",
        resolver=lambda _host, _port: ["93.184.216.34"],
    ))

    assert decision.allowed is True


def test_validate_public_url_rejects_non_http_scheme():
    decision = asyncio.run(validate_public_url("file:///etc/passwd"))

    assert decision.allowed is False
    assert "HTTP" in decision.reason


def test_validate_public_url_rejects_localhost_and_private_ip():
    localhost = asyncio.run(validate_public_url("http://localhost/admin"))
    private = asyncio.run(validate_public_url("http://192.168.1.20/internal"))

    assert localhost.allowed is False
    assert private.allowed is False


def test_validate_public_url_rejects_dns_resolving_to_private_network():
    decision = asyncio.run(validate_public_url(
        "https://public-looking.example/article",
        resolver=lambda _host, _port: ["127.0.0.1"],
    ))

    assert decision.allowed is False
    assert "公网" in decision.reason


def test_validate_public_url_rejects_embedded_credentials():
    decision = asyncio.run(validate_public_url("https://user:pass@example.com/article"))

    assert decision.allowed is False
    assert "凭据" in decision.reason


def test_public_network_backend_connects_to_validated_numeric_ip():
    delegate = _RecordingBackend()
    backend = PublicNetworkBackend(
        resolver=lambda _host, _port: ["93.184.216.34"],
        delegate=delegate,
    )

    asyncio.run(backend.connect_tcp("example.com", 443))

    assert delegate.connected_hosts == [("93.184.216.34", 443)]


def test_public_network_backend_blocks_rebinding_before_connect():
    delegate = _RecordingBackend()
    backend = PublicNetworkBackend(
        resolver=lambda _host, _port: ["127.0.0.1"],
        delegate=delegate,
    )

    with pytest.raises(httpcore.ConnectError, match="non-public"):
        asyncio.run(backend.connect_tcp("public-looking.example", 443))

    assert delegate.connected_hosts == []


def test_fetch_public_html_rejects_non_html_response():
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, headers={"content-type": "application/json"}, json={"ok": True},
        request=request,
    ))

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_public_html(
                client, "https://example.com/data",
                resolver=lambda _host, _port: ["93.184.216.34"],
            )

    assert asyncio.run(run()) is None


def test_fetch_public_html_rejects_oversized_response():
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, headers={"content-type": "text/html; charset=utf-8"},
        content=b"x" * 33, request=request,
    ))

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_public_html(
                client, "https://example.com/article", max_bytes=32,
                resolver=lambda _host, _port: ["93.184.216.34"],
            )

    assert asyncio.run(run()) is None


def test_fetch_public_html_revalidates_redirect_targets():
    transport = httpx.MockTransport(lambda request: httpx.Response(
        302, headers={"location": "http://127.0.0.1/admin"}, request=request,
    ))

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_public_html(
                client, "https://example.com/redirect",
                resolver=lambda _host, _port: ["93.184.216.34"],
            )

    assert asyncio.run(run()) is None


def test_fetch_public_html_rejects_private_connected_peer_after_dns_check():
    class PrivatePeer:
        def get_extra_info(self, key):
            return ("127.0.0.1", 443) if key == "server_addr" else None

    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, headers={"content-type": "text/html"}, content=b"<p>secret</p>",
        extensions={"network_stream": PrivatePeer()}, request=request,
    ))

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_public_html(
                client, "https://example.com/article",
                resolver=lambda _host, _port: ["93.184.216.34"],
            )

    assert asyncio.run(run()) is None


def test_fetch_public_html_uses_exact_media_type_allowlist():
    transport = httpx.MockTransport(lambda request: httpx.Response(
        200, headers={"content-type": "application/x-text/html-evil"},
        content=b"<p>not html</p>", request=request,
    ))

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_public_html(
                client, "https://example.com/article",
                resolver=lambda _host, _port: ["93.184.216.34"],
            )

    assert asyncio.run(run()) is None


def test_fetch_public_json_revalidates_redirect_and_blocks_private_target():
    transport = httpx.MockTransport(lambda request: httpx.Response(
        302, headers={"location": "http://127.0.0.1/metrics"}, request=request,
    ))

    async def run():
        async with httpx.AsyncClient(transport=transport) as client:
            return await fetch_public_json(
                client,
                "https://example.com/api",
                resolver=lambda _host, _port: ["93.184.216.34"],
            )

    assert asyncio.run(run()) is None


def test_fetch_public_json_never_forwards_credentials_across_origins():
    seen = []

    def handler(request):
        seen.append((request.url.host, request.headers.get("authorization")))
        if request.url.host == "api.example":
            return httpx.Response(
                302,
                headers={"location": "https://attacker.example/steal"},
                request=request,
            )
        return httpx.Response(
            200,
            headers={"content-type": "application/json"},
            json={"ok": True},
            request=request,
        )

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await fetch_public_json(
                client,
                "https://api.example/data",
                headers={"Authorization": "Bearer TOPSECRET"},
                resolver=lambda _host, _port: ["93.184.216.34"],
            )

    assert asyncio.run(run()) is None
    assert seen == [("api.example", "Bearer TOPSECRET")]
