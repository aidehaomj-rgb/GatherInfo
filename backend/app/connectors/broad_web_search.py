"""Key-free broad web, news, image and PDF discovery providers."""
from __future__ import annotations

import asyncio
import json
import re
from datetime import timezone
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, quote_plus, unquote, urlparse
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

from app.connectors.base import BaseCollector, CollectResult, FetchItem
from app.connectors._helpers import build_tags, detect_lang, infer_category, result


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "Chrome/124.0 Safari/537.36"
}


SEARCH_LOCALES = {
    "en-US": {"bing": "en-US", "ddg": "us-en", "hl": "en-US", "gl": "US", "ceid": "US:en"},
    "en-IN": {"bing": "en-IN", "ddg": "in-en", "hl": "en-IN", "gl": "IN", "ceid": "IN:en"},
    "hi-IN": {"bing": "hi-IN", "ddg": "in-en", "hl": "hi", "gl": "IN", "ceid": "IN:hi"},
    "ja-JP": {"bing": "ja-JP", "ddg": "jp-jp", "hl": "ja", "gl": "JP", "ceid": "JP:ja"},
    "zh-TW": {"bing": "zh-TW", "ddg": "tw-tzh", "hl": "zh-TW", "gl": "TW", "ceid": "TW:zh-Hant"},
}

_GENERIC_QUERY_TERMS = {
    "2025", "2026", "after", "audit", "bill", "china", "chinese", "components",
    "contract", "customs", "data", "defence", "defense", "export", "from", "government",
    "import", "imports", "investigation", "lading", "military", "official", "procurement",
    "report", "shipment", "supplier", "supply", "trade", "中国", "中國", "进口", "進口",
    "出口", "合同", "契約", "調達", "防衛", "提单", "提單",
}


class BroadWebSearchCollector(BaseCollector):
    """Discover public pages with relevance-filtered DuckDuckGo and Bing results."""

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        items, errors = [], []
        per_query = max(1, min(8, max_items // max(1, len(keywords))))
        yahoo_enabled = len(keywords) <= 4
        semaphore = asyncio.Semaphore(4)
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds, follow_redirects=True,
                                     headers=HEADERS) as client:
            async def search_one(raw_query: str) -> tuple[list[FetchItem], list[str]]:
                query, locale = _query_context(raw_query)
                locale_config = SEARCH_LOCALES[locale]
                query_items: list[FetchItem] = []
                query_errors: list[str] = []
                async with semaphore:
                    try:
                        response = await client.get("https://html.duckduckgo.com/html/", params={
                            "q": query, "kl": locale_config["ddg"],
                        })
                        response.raise_for_status()
                        soup = BeautifulSoup(response.text, "lxml")
                        for row in soup.select(".result"):
                            anchor = row.select_one(".result__a[href]")
                            if not anchor:
                                continue
                            url = _unwrap_duckduckgo_url(anchor["href"])
                            snippet = row.select_one(".result__snippet")
                            title = anchor.get_text(" ", strip=True)
                            summary = snippet.get_text(" ", strip=True) if snippet else ""
                            if not url or _excluded(url) or not _relevant_result(f"{title} {summary}", query):
                                continue
                            query_items.append(_item(
                                title, url, summary, raw_query, "duckduckgo_web", locale=locale,
                            ))
                            if len(query_items) >= per_query:
                                break
                    except Exception as exc:
                        query_errors.append(
                            f"duckduckgo_web: {query[:80]}: {type(exc).__name__}: {exc}"
                        )

                    # Bing is the fallback/second index.  Public Bing results are
                    # region-sensitive, so the same relevance gate is mandatory.
                    if len(_dedupe(query_items)) < per_query:
                        try:
                            response = await client.get("https://www.bing.com/search", params={
                                "q": query, "count": per_query, "setlang": locale_config["bing"],
                                "mkt": locale_config["bing"],
                            })
                            response.raise_for_status()
                            soup = BeautifulSoup(response.text, "lxml")
                            for row in soup.select("li.b_algo"):
                                anchor = row.select_one("h2 a[href]")
                                if not anchor or _excluded(anchor["href"]):
                                    continue
                                snippet = row.select_one(".b_caption p")
                                title = anchor.get_text(" ", strip=True)
                                summary = snippet.get_text(" ", strip=True) if snippet else ""
                                if not _relevant_result(f"{title} {summary}", query):
                                    continue
                                query_items.append(_item(
                                    title, anchor["href"], summary, raw_query, "bing_web", locale=locale,
                                ))
                                if len(_dedupe(query_items)) >= per_query:
                                    break
                        except Exception as exc:
                            query_errors.append(
                                f"bing_web: {query[:80]}: {type(exc).__name__}: {exc}"
                            )

                    # Yahoo's public result page is a useful independent fallback
                    # when DuckDuckGo is unreachable or regional Bing results are
                    # polluted. Keep the same relevance gate and unwrap its tracking
                    # redirect so downstream evidence always stores the real URL.
                    if yahoo_enabled and len(_dedupe(query_items)) < per_query:
                        try:
                            response = await client.get(
                                "https://search.yahoo.com/search",
                                params={"p": query},
                            )
                            response.raise_for_status()
                            soup = BeautifulSoup(response.text, "lxml")
                            for row in soup.select("div.algo"):
                                anchor = row.select_one(".compTitle > a[href]")
                                if not anchor:
                                    continue
                                url = _unwrap_yahoo_url(anchor["href"])
                                if not url or _excluded(url):
                                    continue
                                heading = row.select_one("h3.title")
                                snippet = row.select_one(".compText")
                                title = (
                                    heading.get_text(" ", strip=True)
                                    if heading else anchor.get_text(" ", strip=True)
                                )
                                summary = snippet.get_text(" ", strip=True) if snippet else ""
                                if not _relevant_result(f"{title} {summary}", query):
                                    continue
                                query_items.append(_item(
                                    title, url, summary, raw_query, "yahoo_web", locale=locale,
                                ))
                                if len(_dedupe(query_items)) >= per_query:
                                    break
                        except Exception as exc:
                            query_errors.append(
                                f"yahoo_web: {query[:80]}: {type(exc).__name__}: {exc}"
                            )
                return _dedupe(query_items)[:per_query], query_errors

            responses = await asyncio.gather(*(search_one(query) for query in keywords))
            for query_items, query_errors in responses:
                items.extend(query_items)
                errors.extend(query_errors)
        return result(self._new_run_id(), self.config.id, items[:max_items], errors)


class NewsRSSSearchCollector(BaseCollector):
    """Search locale-aware Google News RSS feeds without API credentials."""

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        items, errors = [], []
        per_query = max(1, min(12, max_items // max(1, len(keywords))))
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds, follow_redirects=True,
                                     headers=HEADERS) as client:
            for raw_query in keywords:
                query, locale = _query_context(raw_query)
                locale_config = SEARCH_LOCALES[locale]
                feeds = ((
                    "google_news",
                    "https://news.google.com/rss/search?"
                    f"q={quote_plus(query)}&hl={locale_config['hl']}&gl={locale_config['gl']}"
                    f"&ceid={locale_config['ceid']}",
                ),)
                for provider, url in feeds:
                    try:
                        response = await client.get(url)
                        response.raise_for_status()
                        root = ElementTree.fromstring(response.content)
                        for node in root.findall(".//item")[:per_query]:
                            title = node.findtext("title") or ""
                            link = node.findtext("link") or ""
                            description = BeautifulSoup(node.findtext("description") or "", "lxml").get_text(" ", strip=True)
                            published = node.findtext("pubDate")
                            if not _relevant_result(f"{title} {description}", query):
                                continue
                            item = _item(title, link, description, raw_query, provider, locale=locale)
                            item.published_at = _rss_date(published)
                            source_node = node.find("source")
                            item.raw_metadata.update({
                                "rss_published_at": published,
                                "publisher": source_node.text if source_node is not None else None,
                                "publisher_url": source_node.get("url") if source_node is not None else None,
                            })
                            items.append(item)
                    except Exception as exc:
                        errors.append(f"{provider}: {query[:80]}: {exc}")
        return result(self._new_run_id(), self.config.id, _dedupe(items)[:max_items], errors)


class ImageSearchCollector(BaseCollector):
    """Discover case images and their source pages via Bing Images."""

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        items, errors = [], []
        per_query = max(1, min(8, max_items // max(1, len(keywords))))
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds, follow_redirects=True,
                                     headers=HEADERS) as client:
            for raw_query in keywords:
                query = _query(raw_query)
                try:
                    response = await client.get("https://www.bing.com/images/search", params={"q": query})
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, "lxml")
                    for anchor in soup.select("a.iusc[m]")[:per_query]:
                        data = json.loads(anchor.get("m") or "{}")
                        source_url = data.get("purl") or ""
                        image_url = data.get("murl") or ""
                        if not source_url or not image_url:
                            continue
                        title = data.get("t") or data.get("desc") or f"Image evidence: {query}"
                        if _excluded(source_url) or not _relevant(title + " " + str(data.get("desc") or ""), query):
                            continue
                        item = _item(title, source_url, data.get("desc") or "", raw_query, "bing_images")
                        item.raw_metadata.update({
                            "media_type": "image", "image_url": image_url,
                            "thumbnail_url": data.get("turl"), "source_host": urlparse(source_url).netloc,
                        })
                        items.append(item)
                except Exception as exc:
                    errors.append(f"bing_images: {query[:80]}: {exc}")
        return result(self._new_run_id(), self.config.id, _dedupe(items)[:max_items], errors)


class PDFSearchCollector(BroadWebSearchCollector):
    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        queries = []
        for raw_query in keywords:
            query, locale = _query_context(raw_query)
            queries.append(f"{locale}||{query} filetype:pdf")
        response = await super().fetch(queries, max_items)
        response.items = [item for item in response.items if _looks_like_pdf(item.url, item.title)]
        for item in response.items:
            item.raw_metadata["media_type"] = "pdf"
            item.raw_metadata["original_query"] = item.raw_metadata.get("query", "").removesuffix(" filetype:pdf")
        return response


def _query(value: str) -> str:
    return str(value).split("||", 1)[-1].strip()


def _query_context(value: str) -> tuple[str, str]:
    raw = str(value)
    prefix, separator, query = raw.partition("||")
    locale = prefix.strip() if separator and prefix.strip() in SEARCH_LOCALES else "en-US"
    return (query.strip() if separator else raw.strip(), locale)


def _item(
    title: str, url: str, snippet: str, query: str, engine: str, *, locale: str = "en-US",
) -> FetchItem:
    text = f"{title} {snippet}"
    return FetchItem(title=title[:500], content=snippet, url=url, summary=snippet[:500],
                     language=detect_lang(text), category=infer_category(title, snippet),
                     suggested_tags=build_tags(title, snippet),
                     raw_metadata={"engine": engine, "query": _query(query), "search_locale": locale})


def _dedupe(items: list[FetchItem]) -> list[FetchItem]:
    seen, output = set(), []
    for item in items:
        key = (item.url or item.title).casefold().strip()
        if key and key not in seen:
            seen.add(key); output.append(item)
    return output


def _excluded(url: str) -> bool:
    host = urlparse(url).netloc.casefold()
    return host == "customs.gov.cn" or host.endswith(".customs.gov.cn")


def _unwrap_duckduckgo_url(value: str) -> str:
    url = f"https:{value}" if value.startswith("//") else value
    parsed = urlparse(url)
    if parsed.netloc.casefold().endswith("duckduckgo.com") and parsed.path == "/l/":
        target = parse_qs(parsed.query).get("uddg", [""])[0]
        return unquote(target)
    return url


def _unwrap_yahoo_url(value: str) -> str:
    parsed = urlparse(value)
    if not parsed.netloc.casefold().endswith("search.yahoo.com"):
        return value
    match = re.search(r"/RU=([^/]+)/RK=", parsed.path)
    if not match:
        return value
    target = unquote(match.group(1))
    return target if target.startswith(("http://", "https://")) else value


def _normalized_search_text(value: str) -> str:
    return re.sub(r"[^a-z0-9\u0900-\u097f\u3040-\u30ff\u3400-\u9fff]+", " ", value.casefold()).strip()


def _relevant_result(text: str, query: str) -> bool:
    """Reject public-search pollution before it consumes document/LLM budget."""
    haystack = _normalized_search_text(text)
    quoted = [
        _normalized_search_text(value)
        for value in re.findall(r'["“”]([^"“”]{3,})["“”]', query)
        if _normalized_search_text(value)
    ]
    if quoted and any(value in haystack for value in quoted):
        return True

    terms = [
        term for term in _normalized_search_text(re.sub(r"\b(?:site|filetype):\S+", " ", query)).split()
        if len(term) >= 3 and term not in _GENERIC_QUERY_TERMS
    ]
    if not terms:
        terms = [
            term for term in _normalized_search_text(query).split()
            if len(term) >= 4 and term not in _GENERIC_QUERY_TERMS
        ]
    matches = sum(term in haystack for term in dict.fromkeys(terms))
    return matches >= (1 if len(terms) <= 2 else 2)


def _rss_date(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).astimezone(timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return None


def _looks_like_pdf(url: str, title: str) -> bool:
    path = urlparse(url).path.casefold()
    return path.endswith(".pdf") or " pdf" in f" {title.casefold()}"


def _relevant(text: str, query: str) -> bool:
    haystack = text.casefold()
    terms = [term.strip('"()[],:;') for term in query.casefold().split()]
    meaningful = [term for term in terms if len(term) >= 4 and not term.startswith(("site:", "filetype:"))]
    return any(term in haystack for term in meaningful[:10])
