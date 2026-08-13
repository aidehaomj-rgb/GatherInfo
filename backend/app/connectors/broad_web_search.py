"""Key-free broad web, news, image and PDF discovery providers."""
from __future__ import annotations

import json
from urllib.parse import quote_plus, urlparse
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup

from app.connectors.base import BaseCollector, CollectResult, FetchItem
from app.connectors._helpers import build_tags, detect_lang, infer_category, result


HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "Chrome/124.0 Safari/537.36"
}


class BroadWebSearchCollector(BaseCollector):
    """Discover public web pages through Bing's public result pages."""

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        items, errors = [], []
        per_query = max(1, min(10, max_items // max(1, len(keywords))))
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds, follow_redirects=True,
                                     headers=HEADERS) as client:
            for raw_query in keywords:
                query = _query(raw_query)
                try:
                    response = await client.get("https://www.bing.com/search", params={
                        "q": query, "count": per_query, "setlang": "en-US",
                    })
                    response.raise_for_status()
                    soup = BeautifulSoup(response.text, "lxml")
                    for row in soup.select("li.b_algo")[:per_query]:
                        anchor = row.select_one("h2 a[href]")
                        if not anchor:
                            continue
                        if _excluded(anchor["href"]):
                            continue
                        snippet = row.select_one(".b_caption p")
                        items.append(_item(anchor.get_text(" ", strip=True), anchor["href"],
                                           snippet.get_text(" ", strip=True) if snippet else "",
                                           raw_query, "bing_web"))
                except Exception as exc:
                    errors.append(f"bing_web: {query[:80]}: {exc}")
        return result(self._new_run_id(), self.config.id, items[:max_items], errors)


class NewsRSSSearchCollector(BaseCollector):
    """Aggregate Google News and Bing News RSS without API credentials."""

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        items, errors = [], []
        per_query = max(1, min(12, max_items // max(1, len(keywords))))
        async with httpx.AsyncClient(timeout=self.config.timeout_seconds, follow_redirects=True,
                                     headers=HEADERS) as client:
            for raw_query in keywords:
                query = _query(raw_query)
                feeds = (("google_news", f"https://news.google.com/rss/search?q={quote_plus(query)}&hl=en-US&gl=US&ceid=US:en"),)
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
                            item = _item(title, link, description, raw_query, provider)
                            item.raw_metadata["rss_published_at"] = published
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
        queries = [f"{_query(query)} filetype:pdf" for query in keywords]
        response = await super().fetch(queries, max_items)
        response.items = [item for item in response.items if _looks_like_pdf(item.url, item.title)]
        for item in response.items:
            item.raw_metadata["media_type"] = "pdf"
            item.raw_metadata["original_query"] = item.raw_metadata.get("query", "").removesuffix(" filetype:pdf")
        return response


def _query(value: str) -> str:
    return str(value).split("||", 1)[-1].strip()


def _item(title: str, url: str, snippet: str, query: str, engine: str) -> FetchItem:
    text = f"{title} {snippet}"
    return FetchItem(title=title[:500], content=snippet, url=url, summary=snippet[:500],
                     language=detect_lang(text), category=infer_category(title, snippet),
                     suggested_tags=build_tags(title, snippet),
                     raw_metadata={"engine": engine, "query": query})


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


def _looks_like_pdf(url: str, title: str) -> bool:
    path = urlparse(url).path.casefold()
    return path.endswith(".pdf") or " pdf" in f" {title.casefold()}"


def _relevant(text: str, query: str) -> bool:
    haystack = text.casefold()
    terms = [term.strip('"()[],:;') for term in query.casefold().split()]
    meaningful = [term for term in terms if len(term) >= 4 and not term.startswith(("site:", "filetype:"))]
    return any(term in haystack for term in meaningful[:10])
