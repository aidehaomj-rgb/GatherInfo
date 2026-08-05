"""Bounded public-HTML fetch helpers for connector detail hydration."""
from __future__ import annotations

import asyncio
import inspect
import ipaddress
import json
import socket
from dataclasses import dataclass
from typing import Awaitable, Callable, Iterable, Any
from urllib.parse import urljoin, urlsplit

import httpcore
import httpx
from httpcore._backends.auto import AutoBackend

DEFAULT_MAX_BYTES = 2 * 1024 * 1024
DEFAULT_MAX_REDIRECTS = 2
HTML_CONTENT_TYPES = ("text/html", "application/xhtml+xml")
XML_CONTENT_TYPES = (
    "application/rss+xml", "application/atom+xml", "application/xml", "text/xml",
)
JSON_CONTENT_TYPES = ("application/json",)
Resolver = Callable[[str, int], Iterable[str] | Awaitable[Iterable[str]]]
_ORIGIN_LOCKS: dict[tuple[int, str], asyncio.Lock] = {}
_ORIGIN_NEXT_ALLOWED: dict[tuple[int, str], float] = {}


class PublicNetworkBackend(httpcore.AsyncNetworkBackend):
    """Resolve once at connect time and connect to that validated numeric IP."""

    def __init__(
        self,
        *,
        resolver: Resolver | None = None,
        delegate: Any | None = None,
    ) -> None:
        self._resolver = resolver or _resolve_host
        self._delegate = delegate or AutoBackend()

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[tuple[int, int, int | bytes]] | None = None,
    ):
        addresses = await _resolve_addresses(host, port, self._resolver)
        if not addresses or any(not _is_global_address(value) for value in addresses):
            raise httpcore.ConnectError("Blocked non-public network target")
        last_error: Exception | None = None
        for address in addresses:
            try:
                return await self._delegate.connect_tcp(
                    address,
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
            except Exception as exc:  # pragma: no cover - address fallback
                last_error = exc
        if last_error is not None:
            raise last_error
        raise httpcore.ConnectError("No public address available")

    async def connect_unix_socket(self, *_args, **_kwargs):
        raise httpcore.ConnectError("Unix sockets are not allowed for public fetches")

    async def sleep(self, seconds: float) -> None:
        await self._delegate.sleep(seconds)


class PublicAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """HTTPX transport whose TCP connection is pinned to a validated public IP."""

    def __init__(
        self,
        *,
        resolver: Resolver | None = None,
        limits: httpx.Limits | None = None,
    ) -> None:
        effective_limits = limits or httpx.Limits(max_connections=10)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=httpx.create_ssl_context(verify=True, trust_env=False),
            max_connections=effective_limits.max_connections,
            max_keepalive_connections=effective_limits.max_keepalive_connections,
            keepalive_expiry=effective_limits.keepalive_expiry,
            retries=0,
            network_backend=PublicNetworkBackend(resolver=resolver),
        )


def public_async_client(
    *,
    timeout: float,
    headers: dict[str, str] | None = None,
    limits: httpx.Limits | None = None,
) -> httpx.AsyncClient:
    """Return a proxy-free client that cannot connect to non-public addresses."""
    effective_limits = limits or httpx.Limits(max_connections=10)
    return httpx.AsyncClient(
        timeout=timeout,
        headers=headers,
        follow_redirects=False,
        trust_env=False,
        limits=effective_limits,
        transport=PublicAsyncHTTPTransport(limits=effective_limits),
    )


@dataclass(frozen=True)
class UrlSafetyDecision:
    allowed: bool
    reason: str
    host: str | None = None


@dataclass(frozen=True)
class SafeFetchResult:
    url: str
    text: str
    content_type: str
    status_code: int


@dataclass(frozen=True)
class SafeJsonResult:
    url: str
    data: Any
    status_code: int


async def validate_public_url(
    url: str,
    *,
    resolver: Resolver | None = None,
) -> UrlSafetyDecision:
    """Reject unsafe schemes, credentials, local hosts, and non-public IPs."""
    try:
        parsed = urlsplit((url or "").strip())
    except ValueError:
        return UrlSafetyDecision(False, "URL 格式无效")
    if parsed.scheme.lower() not in {"http", "https"}:
        return UrlSafetyDecision(False, "只允许 HTTP(S) 公网地址")
    if parsed.username or parsed.password:
        return UrlSafetyDecision(False, "URL 不得包含内嵌凭据")
    host = (parsed.hostname or "").strip().casefold()
    if not host or host == "localhost" or host.endswith(".localhost"):
        return UrlSafetyDecision(False, "不允许访问本机地址", host or None)
    port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    try:
        addresses = [str(ipaddress.ip_address(host))]
    except ValueError:
        try:
            resolved = (resolver or _resolve_host)(host, port)
            addresses = list(await resolved) if inspect.isawaitable(resolved) else list(resolved)
        except (OSError, ValueError, TypeError):
            return UrlSafetyDecision(False, "域名解析失败，无法确认公网地址", host)
    if not addresses:
        return UrlSafetyDecision(False, "域名未解析到公网地址", host)
    if any(not _is_global_address(value) for value in addresses):
        return UrlSafetyDecision(False, "目标解析到非公网地址，已阻止访问", host)
    return UrlSafetyDecision(True, "公网 HTTP(S) 地址", host)


async def fetch_public_html(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    timeout_seconds: float = 15,
    resolver: Resolver | None = None,
    allowed_content_types: tuple[str, ...] = HTML_CONTENT_TYPES,
    minimum_interval_seconds: float = 0,
) -> SafeFetchResult | None:
    """Fetch bounded public HTML and revalidate every redirect target."""
    transport = getattr(client, "_transport", None)
    if isinstance(transport, httpx.AsyncHTTPTransport) and not isinstance(
        transport, PublicAsyncHTTPTransport,
    ):
        return None
    current_url = url
    for redirect_index in range(max_redirects + 1):
        decision = await validate_public_url(current_url, resolver=resolver)
        if not decision.allowed:
            return None
        await _wait_for_origin(current_url, minimum_interval_seconds)
        async with client.stream(
            "GET",
            current_url,
            headers={"User-Agent": "GatherInfo/0.8 (public metadata verification)"},
            timeout=timeout_seconds,
            follow_redirects=False,
        ) as response:
            if not _response_peer_is_public(
                response, require_peer=isinstance(transport, PublicAsyncHTTPTransport),
            ):
                return None
            if response.is_redirect:
                location = response.headers.get("location")
                if not location or redirect_index >= max_redirects:
                    return None
                next_url = urljoin(current_url, location)
                if _origin_key(next_url) != _origin_key(current_url):
                    return None
                current_url = next_url
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").casefold()
            media_type = content_type.split(";", 1)[0].strip()
            if media_type not in frozenset(kind.casefold() for kind in allowed_content_types):
                return None
            payload = await _read_bounded(response, max_bytes)
            if payload is None:
                return None
            encoding = response.encoding or "utf-8"
            return SafeFetchResult(
                url=str(response.url or current_url),
                text=payload.decode(encoding, errors="replace"),
                content_type=content_type,
                status_code=response.status_code,
            )
    return None


def _origin_key(value: str) -> tuple[str, str, int]:
    parsed = urlsplit(value)
    scheme = parsed.scheme.casefold()
    default_port = 443 if scheme == "https" else 80
    return scheme, (parsed.hostname or "").casefold(), parsed.port or default_port


async def fetch_public_json(
    client: httpx.AsyncClient,
    url: str,
    *,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    json_body: Any = None,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_redirects: int = DEFAULT_MAX_REDIRECTS,
    timeout_seconds: float = 30,
    resolver: Resolver | None = None,
    minimum_interval_seconds: float = 0,
) -> SafeJsonResult | None:
    """Request bounded public JSON and revalidate every redirect target."""
    transport = getattr(client, "_transport", None)
    if isinstance(transport, httpx.AsyncHTTPTransport) and not isinstance(
        transport, PublicAsyncHTTPTransport,
    ):
        return None
    current_url = url
    current_method = method.upper()
    current_body = json_body
    for redirect_index in range(max_redirects + 1):
        decision = await validate_public_url(current_url, resolver=resolver)
        if not decision.allowed:
            return None
        await _wait_for_origin(current_url, minimum_interval_seconds)
        async with client.stream(
            current_method,
            current_url,
            params=params if redirect_index == 0 else None,
            headers={"Accept": "application/json", **(headers or {})},
            json=current_body,
            timeout=timeout_seconds,
            follow_redirects=False,
        ) as response:
            if not _response_peer_is_public(
                response, require_peer=isinstance(transport, PublicAsyncHTTPTransport),
            ):
                return None
            if response.is_redirect:
                location = response.headers.get("location")
                if not location or redirect_index >= max_redirects:
                    return None
                next_url = urljoin(current_url, location)
                if _origin_key(next_url) != _origin_key(current_url):
                    return None
                current_url = next_url
                if response.status_code in {301, 302, 303}:
                    current_method = "GET"
                    current_body = None
                continue
            response.raise_for_status()
            media_type = response.headers.get("content-type", "").split(";", 1)[0].strip().casefold()
            if media_type not in JSON_CONTENT_TYPES and not media_type.endswith("+json"):
                return None
            payload = await _read_bounded(response, max_bytes)
            if payload is None:
                return None
            try:
                data = json.loads(payload.decode(response.encoding or "utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                return None
            return SafeJsonResult(str(response.url or current_url), data, response.status_code)
    return None


async def _resolve_host(host: str, port: int) -> list[str]:
    rows = await asyncio.to_thread(socket.getaddrinfo, host, port, type=socket.SOCK_STREAM)
    return list(dict.fromkeys(row[4][0] for row in rows if row[4]))


async def _wait_for_origin(url: str, minimum_interval_seconds: float) -> None:
    global _ORIGIN_LOCKS, _ORIGIN_NEXT_ALLOWED
    interval = max(0.0, float(minimum_interval_seconds or 0))
    if interval <= 0:
        return
    parsed = urlsplit(url)
    default_port = 443 if parsed.scheme.casefold() == "https" else 80
    origin = (
        f"{parsed.scheme.casefold()}://{(parsed.hostname or '').casefold()}:"
        f"{parsed.port or default_port}"
    )
    loop = asyncio.get_running_loop()
    key = (id(loop), origin)
    lock = _ORIGIN_LOCKS.get(key) or asyncio.Lock()
    _ORIGIN_LOCKS = {**_ORIGIN_LOCKS, key: lock}
    async with lock:
        now = loop.time()
        wait_seconds = max(0.0, _ORIGIN_NEXT_ALLOWED.get(key, 0.0) - now)
        if wait_seconds:
            await asyncio.sleep(wait_seconds)
        _ORIGIN_NEXT_ALLOWED = {
            **_ORIGIN_NEXT_ALLOWED,
            key: loop.time() + interval,
        }


async def _resolve_addresses(host: str, port: int, resolver: Resolver) -> list[str]:
    try:
        return [str(ipaddress.ip_address(host))]
    except ValueError:
        resolved = resolver(host, port)
        values = await resolved if inspect.isawaitable(resolved) else resolved
        return list(dict.fromkeys(str(value) for value in values))


def _is_global_address(value: str) -> bool:
    try:
        return ipaddress.ip_address(value).is_global
    except ValueError:
        return False


async def _read_bounded(response: httpx.Response, max_bytes: int) -> bytes | None:
    chunks: list[bytes] = []
    size = 0
    async for chunk in response.aiter_bytes():
        size += len(chunk)
        if size > max(1, max_bytes):
            return None
        chunks = [*chunks, chunk]
    return b"".join(chunks)


def _response_peer_is_public(
    response: httpx.Response, *, require_peer: bool = False,
) -> bool:
    """Reject a private connected peer when the transport exposes its address."""
    stream = response.extensions.get("network_stream")
    if stream is None or not hasattr(stream, "get_extra_info"):
        return not require_peer
    peer = stream.get_extra_info("server_addr")
    if not peer:
        return not require_peer
    address = peer[0] if isinstance(peer, tuple) else peer
    return _is_global_address(str(address))


__all__ = [
    "HTML_CONTENT_TYPES", "JSON_CONTENT_TYPES", "XML_CONTENT_TYPES",
    "PublicAsyncHTTPTransport", "PublicNetworkBackend", "SafeFetchResult",
    "SafeJsonResult", "UrlSafetyDecision", "fetch_public_html",
    "fetch_public_json", "public_async_client", "validate_public_url",
]
