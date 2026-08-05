"""
RSS connector for GatherInfo.
"""
import logging
import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import replace
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from app.connectors.base import (
    BaseCollector, CollectResult, FetchItem,
    JobStatus, SourceConfig, register_collector,
)
from app.safe_fetch import (
    XML_CONTENT_TYPES, fetch_public_html, fetch_public_json, public_async_client,
)
from app.web_content_extractor import extract_article_text

logger = logging.getLogger(__name__)


@register_collector("rss")
class RSSCollector(BaseCollector):
    channel = "rss"

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        feed_url = _feed_url(self.config)
        if not feed_url:
            return self._error("base_url not configured")

        errors: list[str] = []

        async with public_async_client(
            timeout=self.config.timeout_seconds,
            headers=_headers(),
        ) as client:
            try:
                resp = await fetch_public_html(
                    client,
                    feed_url,
                    timeout_seconds=self.config.timeout_seconds,
                    allowed_content_types=XML_CONTENT_TYPES,
                    minimum_interval_seconds=max(
                        float(getattr(self.config, "crawl_delay_seconds", 0) or 0),
                        1.0 / self.config.rate_limit_rps if self.config.rate_limit_rps else 1.0,
                    ),
                )
                if resp is None:
                    raise ValueError("订阅地址非公网 XML、重定向不安全或响应过大")
                raw = resp.text
            except Exception as exc:
                logger.error("RSS HTTP error for source %s: %s", self.config.id, exc)
                return self._error(f"HTTP error: {exc}")

        try:
            root = ET.fromstring(raw)
        except Exception as exc:
            logger.error("RSS XML parse error for source %s: %s", self.config.id, exc)
            return self._error(f"XML parse error: {exc}")

        configured_languages = getattr(self.config, "languages", None)
        fallback_language = (
            str(configured_languages[0])
            if isinstance(configured_languages, list) and configured_languages
            else None
        )
        feed_items = _parse_feed(root, fallback_language=fallback_language)
        auth_config = self.config.auth_config if isinstance(self.config.auth_config, dict) else {}
        filtered = _filter_by_keywords(
            feed_items,
            keywords,
            defer_to_llm=bool(auth_config.get("defer_keyword_filter_to_llm")),
        )
        hydrated = filtered
        if auth_config.get("follow_item_links"):
            async with public_async_client(
                timeout=self.config.timeout_seconds,
                headers=_detail_headers(),
            ) as client:
                hydrated, hydration_errors = await _hydrate_feed_items(
                    client, filtered, feed_url=feed_url,
                    auth_config=auth_config,
                    window_start=self.window_start, window_end=self.window_end,
                    timeout_seconds=self.config.timeout_seconds,
                    minimum_interval_seconds=_minimum_request_interval(self.config),
                )
                errors = [*errors, *hydration_errors]
        logger.info("RSS: %d items from feed, %d after filter for source %s",
                     len(feed_items), len(filtered), self.config.id)
        return CollectResult(
            run_id=self._new_run_id(), source_id=self.config.id,
            status=JobStatus.PARTIAL if errors else JobStatus.COMPLETED,
            items=hydrated[:max_items],
            items_new=min(len(hydrated), max_items),
            items_failed=len(errors), error_log=errors or None,
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


def _detail_headers() -> dict:
    return {
        "User-Agent": "GatherInfo/0.8 (verified official RSS detail hydration)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.8,en;q=0.7",
    }


def _minimum_request_interval(config: SourceConfig) -> float:
    rate_interval = 1.0 / config.rate_limit_rps if config.rate_limit_rps else 1.0
    return max(float(getattr(config, "crawl_delay_seconds", 0) or 0), rate_interval)


async def _hydrate_feed_items(
    client,
    items: list[FetchItem],
    *,
    feed_url: str,
    auth_config: dict,
    window_start: datetime | None,
    window_end: datetime | None,
    timeout_seconds: float,
    minimum_interval_seconds: float,
) -> tuple[list[FetchItem], list[str]]:
    hydrated: list[FetchItem] = []
    errors: list[str] = []
    detail_count = 0
    limit = max(0, min(int(auth_config.get("max_detail_items") or 6), 20))
    for item in items:
        if detail_count >= limit or not _should_hydrate(
            item, feed_url, auth_config, window_start, window_end,
        ):
            hydrated = [*hydrated, item]
            continue
        detail_count += 1
        enriched_items, error = await _hydrate_item(
            client, item, timeout_seconds=timeout_seconds,
            minimum_interval_seconds=minimum_interval_seconds,
            max_content_chars=int(auth_config.get("max_detail_content_chars") or 30_000),
            feed_url=feed_url, auth_config=auth_config,
        )
        hydrated = [*hydrated, *enriched_items]
        errors = [*errors, error] if error else errors
    return hydrated, errors


async def _hydrate_item(
    client,
    item: FetchItem,
    *,
    timeout_seconds: float,
    minimum_interval_seconds: float,
    max_content_chars: int,
    feed_url: str,
    auth_config: dict,
) -> tuple[list[FetchItem], str | None]:
    if auth_config.get("detail_fetch_strategy") == "eu_presscorner_api":
        return await _hydrate_eu_presscorner_item(
            client, item, feed_url=feed_url, auth_config=auth_config,
            timeout_seconds=timeout_seconds,
            minimum_interval_seconds=minimum_interval_seconds,
            max_content_chars=max_content_chars,
        )
    try:
        response = await fetch_public_html(
            client, str(item.url), timeout_seconds=timeout_seconds,
            minimum_interval_seconds=minimum_interval_seconds,
        )
        if response is None:
            return [item], f"详情页未通过公网 HTML 安全校验：{item.url}"
        extracted = extract_article_text(response.text, response.url)
        content = str(extracted.get("content") or "").strip()[:max(1000, max_content_chars)]
        if len(content) <= len((item.content or "").strip()):
            return [item], f"详情页未提取到更完整正文：{item.url}"
        return [_enriched_item(
            item, content=content,
            summary=str(extracted.get("summary") or item.summary or ""),
            detail_url=response.url, strategy="html",
        )], None
    except Exception as exc:
        return [item], f"详情页补全失败：{item.url}；{exc}"


async def _hydrate_eu_presscorner_item(
    client,
    item: FetchItem,
    *,
    feed_url: str,
    auth_config: dict,
    timeout_seconds: float,
    minimum_interval_seconds: float,
    max_content_chars: int,
) -> tuple[list[FetchItem], str | None]:
    endpoint = str(auth_config.get("detail_api_endpoint") or "").strip()
    reference = _eu_presscorner_reference(item.url)
    if not reference or not _allowed_eu_detail_api(feed_url, endpoint):
        return [item], f"欧委会详情 API 配置或文档引用无效：{item.url}"
    try:
        response = await fetch_public_json(
            client, endpoint,
            params={"reference": reference, "language": "en"},
            headers={
                "Origin": _origin(feed_url),
                "Referer": str(item.url),
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout_seconds=timeout_seconds,
            minimum_interval_seconds=minimum_interval_seconds,
        )
        payload = response.data if response and isinstance(response.data, dict) else {}
        resource = payload.get("docuLanguageResource")
        html = resource.get("htmlContent") if isinstance(resource, dict) else None
        document_type = payload.get("docutypeResource")
        document_code = (
            str(document_type.get("code") or "").upper()
            if isinstance(document_type, dict) else ""
        )
        if document_code == "MEX":
            sections = _split_eu_daily_news(item, str(html or ""), endpoint)
            if sections:
                return sections, None
        extracted = extract_article_text(f"<article>{html or ''}</article>", endpoint)
        content = str(extracted.get("content") or "").strip()[:max(1000, max_content_chars)]
        if len(content) <= len((item.content or "").strip()):
            return [item], f"欧委会详情 API 未返回更完整正文：{item.url}"
        return [_enriched_item(
            item, content=content,
            summary=str(extracted.get("summary") or item.summary or ""),
            detail_url=endpoint, strategy="eu_presscorner_api",
        )], None
    except Exception as exc:
        return [item], f"欧委会详情 API 补全失败：{item.url}；{exc}"


def _split_eu_daily_news(
    item: FetchItem,
    html: str,
    detail_url: str,
) -> list[FetchItem]:
    soup = BeautifulSoup(html, "lxml")
    sections: tuple[tuple[str, tuple[str, ...]], ...] = ()
    title = ""
    paragraphs: tuple[str, ...] = ()
    for node in soup.find_all("p"):
        text = node.get_text(" ", strip=True)
        is_heading = bool(text and node.find("strong") and node.find("u"))
        if is_heading:
            sections = _finish_section(sections, title, paragraphs)
            title, paragraphs = text, ()
        elif title and text:
            paragraphs = (*paragraphs, text)
    sections = _finish_section(sections, title, paragraphs)
    return [
        _section_item(item, section_title, section_body, detail_url)
        for section_title, section_paragraphs in sections
        if (section_body := "\n\n".join(section_paragraphs))
    ]


def _finish_section(
    sections: tuple[tuple[str, tuple[str, ...]], ...],
    title: str,
    paragraphs: tuple[str, ...],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    generic = {"STATEMENTS", "ANNOUNCEMENTS", "OTHER NEWS", "NEWS"}
    body_length = sum(len(value) for value in paragraphs)
    if not title or title.strip().upper() in generic or body_length < 120:
        return sections
    return (*sections, (title.strip(), paragraphs))


def _section_item(
    item: FetchItem,
    title: str,
    content: str,
    detail_url: str,
) -> FetchItem:
    section_id = hashlib.sha256(
        f"{title}\n{content}".encode("utf-8")
    ).hexdigest()[:16]
    parent_url = str(item.url or "")
    return replace(
        item, title=title, content=content, summary=content[:500],
        url=_section_url(parent_url, section_id),
        raw_metadata={
            **(item.raw_metadata or {}),
            "detail_hydrated": True,
            "detail_url": detail_url,
            "detail_strategy": "eu_presscorner_api",
            "parent_url": parent_url,
            "roundup_title": item.title,
            "source_section_id": section_id,
        },
    )


def _section_url(parent_url: str, section_id: str) -> str:
    parsed = urlsplit(parent_url)
    query = [
        (key, value) for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key != "traderadar_section"
    ]
    return urlunsplit((
        parsed.scheme, parsed.netloc, parsed.path,
        urlencode([*query, ("traderadar_section", section_id)]), parsed.fragment,
    ))


def _enriched_item(
    item: FetchItem,
    *,
    content: str,
    summary: str,
    detail_url: str,
    strategy: str,
) -> FetchItem:
    return replace(
        item, content=content, summary=summary[:500] or None,
        raw_metadata={
            **(item.raw_metadata or {}),
            "detail_hydrated": True,
            "detail_url": detail_url,
            "detail_strategy": strategy,
        },
    )


def _eu_presscorner_reference(value: str | None) -> str | None:
    try:
        token = (urlsplit(value or "").path.rsplit("/", 1)[-1]).replace("_", "/")
    except ValueError:
        return None
    normalized = token.upper()
    return normalized if re.fullmatch(r"[A-Z]{2,20}/\d{2,4}/\d{1,8}", normalized) else None


def _allowed_eu_detail_api(feed_url: str, endpoint: str) -> bool:
    try:
        feed = urlsplit(feed_url)
        detail = urlsplit(endpoint)
    except ValueError:
        return False
    return (
        feed.scheme.casefold() == detail.scheme.casefold() == "https"
        and (feed.hostname or "").casefold() == (detail.hostname or "").casefold()
        and detail.path == "/commission/presscorner/api/documents"
    )


def _origin(value: str) -> str:
    parsed = urlsplit(value)
    return f"{parsed.scheme}://{parsed.netloc}"


def _should_hydrate(
    item: FetchItem,
    feed_url: str,
    auth_config: dict,
    window_start: datetime | None,
    window_end: datetime | None,
) -> bool:
    if not item.url or len((item.content or "").strip()) >= int(
        auth_config.get("min_detail_content_chars") or 800
    ):
        return False
    if not _allowed_item_url(feed_url, item.url, auth_config):
        return False
    published = _coerce_published(item.published_at)
    if window_start and (published is None or published < window_start):
        return False
    if window_end and (published is None or published >= window_end):
        return False
    return True


def _allowed_item_url(feed_url: str, item_url: str, auth_config: dict) -> bool:
    try:
        feed = urlsplit(feed_url)
        item = urlsplit(item_url)
    except ValueError:
        return False
    prefixes = auth_config.get("item_path_prefixes")
    allowed_prefixes = [str(value) for value in prefixes] if isinstance(prefixes, list) else []
    return bool(allowed_prefixes) and (
        feed.scheme.casefold() == "https"
        and item.scheme.casefold() == "https"
        and (feed.hostname or "").casefold() == (item.hostname or "").casefold()
        and any((item.path or "/").startswith(prefix) for prefix in allowed_prefixes)
    )


def _parse_published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc).astimezone(timezone.utc)


def _feed_url(config: SourceConfig) -> str:
    base = (config.base_url or "").strip()
    endpoint = (config.api_endpoint or "").strip()
    if endpoint.startswith("http"):
        return endpoint
    if base and endpoint:
        return urljoin(base if base.endswith("/") else base + "/", endpoint.lstrip("/"))
    return base or endpoint


def _parse_feed(
    root: ET.Element,
    fallback_language: str | None = None,
) -> list[FetchItem]:
    items: list[FetchItem] = []

    rss1_ns = "http://purl.org/rss/1.0/"
    dc_ns = "http://purl.org/dc/elements/1.1/"
    content_ns = "http://purl.org/rss/1.0/modules/content/"
    rss1_items = root.findall(f"{{{rss1_ns}}}item")
    if rss1_items:
        for entry in rss1_items:
            title = _text(entry, f"{{{rss1_ns}}}title")
            link = _text(entry, f"{{{rss1_ns}}}link")
            summary = _text(entry, f"{{{rss1_ns}}}description")
            content = _text(entry, f"{{{content_ns}}}encoded")
            published = _text(entry, f"{{{dc_ns}}}date")
            category = _text(entry, f"{{{dc_ns}}}type")
            if title:
                items.append(FetchItem(
                    title=title, content=content or summary, url=link,
                    summary=summary[:300] if summary else None,
                    published_at=published or None, category=category or None,
                    language=_guess_lang(entry) or fallback_language,
                    raw_metadata={"feed_type": "rss1"},
                ))
        return items

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
                    published_at=updated,
                    language=_guess_lang(entry) or fallback_language,
                    raw_metadata={"feed_type": "atom"},
                ))
        return items

    for elem in channel.findall("item"):
        title = _text(elem, "title")
        link = _text(elem, "link")
        desc = _text(elem, "description")
        pub = _text(elem, "pubDate")
        cat = _text(elem, "category")
        published = _parse_published_at(pub)
        if title:
            items.append(FetchItem(
                title=title, content=desc, url=link,
                summary=desc[:300] if desc else None,
                published_at=published, category=cat,
                language=_guess_lang(elem) or fallback_language,
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
    return ""


def _parse_published_at(value: str) -> str | None:
    if not value:
        return None
    try:
        published = parsedate_to_datetime(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    else:
        published = published.astimezone(timezone.utc)
    return published.isoformat()


def _coerce_published(value: str | None) -> datetime | None:
    """Convert an ISO string or date string to a timezone-aware datetime."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except (ValueError, TypeError):
        try:
            dt = parsedate_to_datetime(value)
        except (TypeError, ValueError, OverflowError):
            return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _filter_by_keywords(
    items: list[FetchItem],
    keywords: list[str],
    *,
    defer_to_llm: bool = False,
) -> list[FetchItem]:
    if not keywords or defer_to_llm:
        return list(items)
    # RSS feeds are already topically curated by the publisher.  Requiring
    # literal keyword matches here discards valid trade-policy news that uses
    # different wording (e.g. "memorandum", "regulation", "decree").  Keep all
    # items and let the downstream engine's keyword filter + LLM review handle
    # relevance.
    return list(items)
