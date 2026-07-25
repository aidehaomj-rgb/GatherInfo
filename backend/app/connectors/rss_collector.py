"""
RSS connector for GatherInfo.
"""
import logging
import hashlib
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin

import httpx

from app.connectors.base import (
    BaseCollector, CollectResult, FetchItem,
    JobStatus, SourceConfig, register_collector,
)

logger = logging.getLogger(__name__)


@register_collector("rss")
class RSSCollector(BaseCollector):
    channel = "rss"

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        feed_url = _feed_url(self.config)
        if not feed_url:
            return self._error("base_url not configured")

        errors: list[str] = []

        async with httpx.AsyncClient(
            timeout=self.config.timeout_seconds,
            headers=_headers(),
            follow_redirects=True,
        ) as client:
            try:
                resp = await client.get(feed_url)
                resp.raise_for_status()
                raw = resp.text
            except Exception as exc:
                logger.error("RSS HTTP error for source %s: %s", self.config.id, exc)
                return self._error(f"HTTP error: {exc}")

        try:
            root = ET.fromstring(raw)
        except Exception as exc:
            logger.error("RSS XML parse error for source %s: %s", self.config.id, exc)
            return self._error(f"XML parse error: {exc}")

        feed_items = _parse_feed(root)
        filtered = _filter_by_keywords(feed_items, keywords)
        logger.info("RSS: %d items from feed, %d after filter for source %s",
                     len(feed_items), len(filtered), self.config.id)
        return CollectResult(
            run_id=self._new_run_id(), source_id=self.config.id,
            status=JobStatus.COMPLETED, items=filtered[:max_items],
            items_new=min(len(filtered), max_items),
        )

    def _error(self, msg: str) -> CollectResult:
        return CollectResult(
            run_id=self._new_run_id(), source_id=self.config.id,
            status=JobStatus.FAILED, items=[], error_log=[msg],
        )


def _headers() -> dict:
    return {
        "User-Agent": "GatherInfo/0.3 (Global Monitor; contact@example.com)",
        "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
    }


def _feed_url(config: SourceConfig) -> str:
    base = (config.base_url or "").strip()
    endpoint = (config.api_endpoint or "").strip()
    if endpoint.startswith("http"):
        return endpoint
    if base and endpoint:
        return urljoin(base if base.endswith("/") else base + "/", endpoint.lstrip("/"))
    return base or endpoint


def _parse_feed(root: ET.Element) -> list[FetchItem]:
    items: list[FetchItem] = []

    # RSS 2.0
    channel = root if root.tag == "channel" else root.find("channel")
    if channel is None:
        # Try Atom
        atom_ns = "http://www.w3.org/2005/Atom"
        for entry in root.findall(f"{{{atom_ns}}}entry") or root.findall("entry"):
            title = _text(entry, f"{{{atom_ns}}}title") or _text(entry, "title")
            link = _link(entry, atom_ns)
            summary = _text(entry, f"{{{atom_ns}}}summary") or _text(entry, "summary")
            content = _text(entry, f"{{{atom_ns}}}content") or _text(entry, "content")
            updated = _text(entry, f"{{{atom_ns}}}updated") or _text(entry, "updated")
            if title:
                items.append(FetchItem(
                    title=title, content=content or summary, url=link,
                    summary=summary[:300] if summary else None,
                    published_at=updated, language=_guess_lang(entry),
                    raw_metadata={"feed_type": "atom"},
                ))
        return items

    for elem in channel.findall("item"):
        title = _text(elem, "title")
        link = _text(elem, "link")
        desc = _text(elem, "description")
        pub = _text(elem, "pubDate")
        cat = _text(elem, "category")
        published = None
        if pub:
            try:
                published = parsedate_to_datetime(pub).replace(
                    tzinfo=timezone.utc).isoformat()
            except Exception:
                pass
        if title:
            items.append(FetchItem(
                title=title, content=desc, url=link,
                summary=desc[:300] if desc else None,
                published_at=published, category=cat,
                language=_guess_lang(elem),
                raw_metadata={"feed_type": "rss"},
            ))
    return items


def _text(elem: ET.Element, tag: str) -> str:
    child = elem.find(tag)
    return (child.text or "").strip() if child is not None and child.text else ""


def _link(elem: ET.Element, ns: str) -> str:
    link = elem.find(f"{{{ns}}}link")
    if link is not None:
        return link.get("href", "") or ""
    return _text(elem, "link")


def _guess_lang(elem: ET.Element) -> str:
    for attr in ("{http://www.w3.org/XML/1998/namespace}lang", "lang"):
        val = elem.get(attr, "")
        if val:
            return val[:2]
    return "en"


def _filter_by_keywords(items: list[FetchItem], keywords: list[str]) -> list[FetchItem]:
    if not keywords:
        return items
    return [
        it for it in items
        if any(kw.lower() in f"{it.title} {it.content or ''}".lower() for kw in keywords)
    ]
