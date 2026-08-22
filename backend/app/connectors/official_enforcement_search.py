"""Key-free search adapters for official border-enforcement news indexes."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
import html
import logging
import re
import unicodedata
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

import httpx
from bs4 import BeautifulSoup

from app.connectors.base import BaseCollector, CollectResult, FetchItem
from app.connectors._helpers import detect_lang, infer_category, result
from app.safe_fetch import public_async_client
from app.web_content_extractor import extract_article_text


logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": "GatherInfo/0.3 (public-source risk monitor)",
    "Accept": "application/json,text/html,application/xhtml+xml",
}
_ENFORCEMENT_TERMS = (
    "seiz", "smuggl", "arrest", "intercept", "confiscat", "detain",
    "charge", "prosecut", "convict", "sentenc", "raid", "illegal",
    "contraband", "drug", "weapon", "tobacco", "counterfeit",
    "apreend", "retém", "retem", "incaut", "decomis", "contrabando",
    "droga", "cocaina", "maconha", "cigarro", "arma", "prisao",
    "detenido", "detencion", "condena", "fiscalizacion",
)


class OfficialEnforcementSearchCollector(BaseCollector):
    """Discover cases through public APIs exposed by official agencies."""

    channel = "official_enforcement_search"

    async def fetch(
        self,
        keywords: list[str],
        max_items: int = 100,
    ) -> CollectResult:
        async with public_async_client(
            timeout=max(20, self.config.timeout_seconds),
            headers=_HEADERS,
        ) as client:
            responses = await asyncio.gather(
                self._fetch_govuk(client),
                self._fetch_cbsa(client),
                self._fetch_abf(client),
                self._fetch_nz_customs(client),
                self._fetch_ph_customs(client),
                self._fetch_brazil_receita(client),
                return_exceptions=True,
            )

        items: list[FetchItem] = []
        errors: list[str] = []
        for response in responses:
            if isinstance(response, Exception):
                errors.append(f"Official enforcement search failed: {response}")
                continue
            provider_items, provider_errors = response
            items.extend(provider_items)
            errors.extend(provider_errors)

        items.sort(key=lambda item: str(item.published_at or ""), reverse=True)
        return result(
            self._new_run_id(), self.config.id, items[:max_items], errors
        )

    async def _fetch_govuk(
        self, client: httpx.AsyncClient
    ) -> tuple[list[FetchItem], list[str]]:
        url = "https://www.gov.uk/api/search.json"
        params = {
            "filter_organisations": "border-force",
            "order": "-public_timestamp",
            "count": 100,
        }
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            rows = response.json().get("results", [])
            items = [
                self._item(
                    title=row.get("title"),
                    content=row.get("description"),
                    url=urljoin("https://www.gov.uk", row.get("link") or ""),
                    published_at=row.get("public_timestamp"),
                    jurisdiction="United Kingdom",
                    authority="UK Border Force",
                    provider="govuk_search_api",
                    date_verification="official_index",
                )
                for row in rows
                if row.get("format") == "news_story"
                and _looks_like_enforcement(row.get("title"), row.get("description"))
            ]
            return [item for item in items if item], []
        except Exception as exc:
            logger.warning("GOV.UK enforcement search failed: %s", exc)
            return [], [f"GOV.UK search unavailable: {exc}"]

    async def _fetch_cbsa(
        self, client: httpx.AsyncClient
    ) -> tuple[list[FetchItem], list[str]]:
        url = "https://api.io.canada.ca/io-server/gc/news/en/v2"
        start = (self.window_start or datetime.now(timezone.utc)).strftime("%Y-%m-%d")
        params = {
            "dept": "canadaborderservicesagency",
            "sort": "publishedDate",
            "orderBy": "desc",
            "pick": 100,
            "publishedDate>": start,
        }
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            rows = response.json().get("feed", {}).get("entry", [])
            items = [
                self._item(
                    title=row.get("title"),
                    content=row.get("teaser"),
                    url=row.get("link"),
                    published_at=row.get("publishedDate"),
                    jurisdiction="Canada",
                    authority="Canada Border Services Agency",
                    provider="canada_news_api",
                    date_verification="official_index",
                )
                for row in rows
                if _looks_like_enforcement(row.get("title"), row.get("teaser"))
            ]
            return [item for item in items if item], []
        except Exception as exc:
            logger.warning("CBSA enforcement search failed: %s", exc)
            return [], [f"CBSA search unavailable: {exc}"]

    async def _fetch_abf(
        self, client: httpx.AsyncClient
    ) -> tuple[list[FetchItem], list[str]]:
        url = "https://www.abf.gov.au/_api/search/query"
        params = {
            "querytext": "'contenttype:Internet.NewsRoom'",
            "selectproperties": (
                "'Title,Path,Internet.NewsRoom.ArticleDate,"
                "Internet.GolbalMetaData.GlbDocDescription'"
            ),
            "rowlimit": "100",
            "sortlist": "'Internet.NewsRoom.ArticleDate:descending'",
            "trimduplicates": "false",
            "querytemplatepropertiesurl": (
                "'spfile://webroot/queryparametertemplate.xml'"
            ),
        }
        try:
            response = await client.get(
                url,
                params=params,
                headers={**_HEADERS, "Accept": "application/json;odata=verbose"},
            )
            response.raise_for_status()
            payload = response.json()
            root = payload.get("d", {}).get("query") or payload
            table = (
                root
                .get("PrimaryQueryResult", {})
                .get("RelevantResults", {})
                .get("Table", {})
                .get("Rows", [])
            )
            if isinstance(table, dict):
                table = table.get("results", [])
            items: list[FetchItem] = []
            for row in table:
                cells = row.get("Cells", [])
                if isinstance(cells, dict):
                    cells = cells.get("results", [])
                values = {
                    cell.get("Key"): cell.get("Value")
                    for cell in cells
                }
                title = values.get("Title")
                description = values.get(
                    "Internet.GolbalMetaData.GlbDocDescription"
                )
                if not _looks_like_enforcement(title, description):
                    continue
                path = str(values.get("Path") or values.get("OriginalPath") or "")
                path = path.replace(
                    "http://borderforceinternal.internet.zone",
                    "https://www.abf.gov.au",
                ).replace(
                    "https://borderforceinternal.internet.zone",
                    "https://www.abf.gov.au",
                )
                item = self._item(
                    title=title,
                    content=description,
                    url=path,
                    published_at=values.get("Internet.NewsRoom.ArticleDate"),
                    jurisdiction="Australia",
                    authority="Australian Border Force",
                    provider="abf_sharepoint_search",
                    date_verification="official_index",
                )
                if item:
                    items.append(item)
            return items, []
        except Exception as exc:
            logger.warning("ABF enforcement search failed: %s", exc)
            return [], [f"ABF search unavailable: {exc}"]

    async def _fetch_nz_customs(
        self, client: httpx.AsyncClient
    ) -> tuple[list[FetchItem], list[str]]:
        url = "https://www.customs.govt.nz/api/news/items"
        params = {
            "searchTerm": "",
            "pageNumber": 1,
            "pageSize": 60,
            "sortAscending": "true",
            "sortBy": "Recent",
            "parentId": 20002,
        }
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            rows = response.json().get("results", [])
            candidates = [
                row for row in rows
                if _looks_like_enforcement(row.get("title"), row.get("description"))
            ][:15]

            async def hydrate(row: dict) -> FetchItem | None:
                page_url = urljoin(
                    "https://www.customs.govt.nz", row.get("url") or ""
                )
                try:
                    page = await client.get(page_url)
                    page.raise_for_status()
                    extracted = extract_article_text(page.text, page_url)
                    published_at = (
                        extracted.get("published_at")
                        or _extract_human_date(page.text)
                    )
                except Exception as exc:
                    logger.warning("NZ Customs detail fetch failed for %s: %s", page_url, exc)
                    extracted = {}
                    published_at = None
                return self._item(
                    title=row.get("title"),
                    content=extracted.get("content") or row.get("description"),
                    url=page_url,
                    published_at=published_at,
                    jurisdiction="New Zealand",
                    authority="New Zealand Customs Service",
                    provider="nz_customs_news_api",
                    date_verification=(
                        "source_page" if published_at else "unverified"
                    ),
                )

            hydrated = await asyncio.gather(
                *[hydrate(row) for row in candidates],
                return_exceptions=True,
            )
            items = [item for item in hydrated if isinstance(item, FetchItem)]
            return items, []
        except Exception as exc:
            logger.warning("New Zealand Customs search failed: %s", exc)
            return [], [f"New Zealand Customs search unavailable: {exc}"]

    async def _fetch_ph_customs(
        self, client: httpx.AsyncClient
    ) -> tuple[list[FetchItem], list[str]]:
        """Read Philippine Bureau of Customs releases through its public WP API."""
        url = "https://customs.gov.ph/wp-json/wp/v2/posts"
        params = {
            "categories": 106,
            "per_page": 100,
            "orderby": "date",
            "order": "desc",
            "_fields": "date_gmt,link,title,excerpt,content",
        }
        try:
            response = await client.get(
                url,
                params=params,
                headers={
                    **_HEADERS,
                    "User-Agent": "GatherInfo/0.8 (public-source risk monitor)",
                    "Referer": "https://customs.gov.ph/category/media-releases/",
                },
            )
            response.raise_for_status()
            rows = response.json()
            items = [
                self._item(
                    title=_wp_text(row.get("title")),
                    content=(
                        _wp_text(row.get("content"))
                        or _wp_text(row.get("excerpt"))
                    ),
                    url=row.get("link"),
                    published_at=f"{row.get('date_gmt')}Z",
                    jurisdiction="Philippines",
                    authority="Philippine Bureau of Customs",
                    provider="philippines_customs_wp_api",
                    date_verification="official_index",
                )
                for row in rows
                if _looks_like_enforcement(
                    _wp_text(row.get("title")),
                    _wp_text(row.get("excerpt")),
                )
            ]
            return [item for item in items if item], []
        except Exception as exc:
            logger.warning("Philippine Customs search failed: %s", exc)
            return [], [f"Philippine Customs search unavailable: {exc}"]

    async def _fetch_brazil_receita(
        self, client: httpx.AsyncClient
    ) -> tuple[list[FetchItem], list[str]]:
        """Discover Receita Federal enforcement stories from its public listings."""
        listing_urls = (
            "https://www.gov.br/receitafederal/pt-br/assuntos/noticias",
            "https://www.gov.br/receitafederal/pt-br/assuntos/noticias/contrabando",
        )
        try:
            listing_pages = await asyncio.gather(
                *[client.get(url) for url in listing_urls],
                return_exceptions=True,
            )
            links: list[tuple[str, str]] = []
            seen: set[str] = set()
            for page in listing_pages:
                if isinstance(page, Exception):
                    continue
                page.raise_for_status()
                soup = BeautifulSoup(page.text, "lxml")
                for anchor in soup.select("a[href]"):
                    page_url = urljoin(str(page.url), anchor.get("href") or "")
                    if not re.search(
                        r"/assuntos/noticias/\d{4}/[^/]+/[^/?#]+$", page_url
                    ):
                        continue
                    title = " ".join(anchor.get_text(" ", strip=True).split())
                    if (
                        page_url in seen
                        or not title
                        or not _looks_like_enforcement(title, "")
                    ):
                        continue
                    seen.add(page_url)
                    links.append((title, page_url))

            semaphore = asyncio.Semaphore(6)

            async def hydrate(title: str, page_url: str) -> FetchItem | None:
                async with semaphore:
                    try:
                        page = await client.get(page_url)
                        page.raise_for_status()
                        extracted = extract_article_text(page.text, page_url)
                        published_at = (
                            extracted.get("published_at")
                            or _extract_portuguese_date(page.text)
                        )
                    except Exception as exc:
                        logger.warning(
                            "Receita Federal detail fetch failed for %s: %s",
                            page_url,
                            exc,
                        )
                        return None
                return self._item(
                    title=extracted.get("title") or title,
                    content=extracted.get("content") or title,
                    url=page_url,
                    published_at=published_at,
                    jurisdiction="Brazil",
                    authority="Receita Federal do Brasil",
                    provider="brazil_receita_listing",
                    date_verification=(
                        "source_page" if published_at else "unverified"
                    ),
                )

            hydrated = await asyncio.gather(
                *[hydrate(title, page_url) for title, page_url in links[:30]],
                return_exceptions=True,
            )
            items = [item for item in hydrated if isinstance(item, FetchItem)]
            return items, []
        except Exception as exc:
            logger.warning("Receita Federal search failed: %s", exc)
            return [], [f"Receita Federal search unavailable: {exc}"]

    def _item(
        self,
        *,
        title: object,
        content: object,
        url: object,
        published_at: object,
        jurisdiction: str,
        authority: str,
        provider: str,
        date_verification: str,
    ) -> FetchItem | None:
        clean_title = str(title or "").strip()
        clean_url = str(url or "").strip()
        clean_content = str(content or "").strip()
        if not clean_title or not clean_url:
            return None
        published = _parse_date(published_at)
        return FetchItem(
            title=clean_title,
            content=clean_content or clean_title,
            summary=(clean_content or clean_title)[:700],
            url=clean_url,
            published_at=published,
            language=detect_lang(f"{clean_title} {clean_content}"),
            category=infer_category(clean_title, clean_content),
            quality_score=0.82,
            relevance_score=0.82,
            raw_metadata={
                "engine": "official_enforcement_search",
                "official_search_provider": provider,
                "search_jurisdiction": jurisdiction,
                "search_authority": authority,
                "date_verification": date_verification,
                "allow_undated_results": False,
            },
        )


def _looks_like_enforcement(title: object, content: object) -> bool:
    text = unicodedata.normalize(
        "NFKD", f"{title or ''} {content or ''}".casefold()
    )
    text = "".join(char for char in text if not unicodedata.combining(char))
    return any(term in text for term in _ENFORCEMENT_TERMS)


def _wp_text(value: object) -> str:
    if isinstance(value, dict):
        value = value.get("rendered")
    text = BeautifulSoup(str(value or ""), "lxml").get_text(" ", strip=True)
    return " ".join(html.unescape(text).split())


def _parse_date(value: object) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        return None


def _extract_human_date(html: str) -> str | None:
    match = re.search(
        r"\b(\d{1,2})\s+"
        r"(January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+(\d{4})\b",
        html,
        re.IGNORECASE,
    )
    if not match:
        return None
    try:
        parsed = datetime.strptime(" ".join(match.groups()), "%d %B %Y")
        return parsed.replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def _extract_portuguese_date(page_html: str) -> str | None:
    soup = BeautifulSoup(page_html, "lxml")
    node = soup.select_one(".documentPublished .value")
    text = " ".join(node.get_text(" ", strip=True).split()) if node else ""
    match = re.search(
        r"\b(\d{1,2})/(\d{1,2})/(\d{4})(?:\s+(\d{1,2})h(\d{2}))?",
        text,
    )
    if not match:
        return None
    day, month, year, hour, minute = match.groups()
    parsed = datetime(
        int(year),
        int(month),
        int(day),
        int(hour or 0),
        int(minute or 0),
        tzinfo=ZoneInfo("America/Sao_Paulo"),
    )
    return parsed.astimezone(timezone.utc).isoformat()
