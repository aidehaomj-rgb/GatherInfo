"""
Web scraper connector for GatherInfo.
"""
import logging
import re
import asyncio
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from app.connectors.base import (
    BaseCollector, CollectResult, FetchItem,
    JobStatus, SourceConfig, register_collector,
)
from app.connectors._helpers import detect_lang, infer_category, build_tags
from app.web_content_extractor import extract_article_text
from app.safe_fetch import fetch_public_html, public_async_client

logger = logging.getLogger(__name__)


@register_collector("web_scrape")
class WebScrapeCollector(BaseCollector):
    channel = "web_scrape"

    async def fetch(self, keywords: list[str], max_items: int = 100) -> CollectResult:
        if not self.config.base_url:
            logger.warning("base_url not configured for source %s", self.config.id)
            return self._error("base_url not configured")

        cfg = self.config
        ac = cfg.auth_config or {}
        urls = _build_urls(cfg.base_url, ac.get("max_pages", 1))

        items: list[FetchItem] = []
        errors: list[str] = []
        seen: set[str] = set()

        async with public_async_client(
            timeout=cfg.timeout_seconds,
            headers=_scrape_headers(),
        ) as client:
            for url in urls:
                if len(items) >= max_items:
                    break
                try:
                    resp = await fetch_public_html(
                        client, url, timeout_seconds=cfg.timeout_seconds,
                        minimum_interval_seconds=_minimum_request_interval(cfg),
                    )
                    if resp is None:
                        raise ValueError("URL 非公网 HTML、重定向不安全或响应过大")
                    soup = BeautifulSoup(resp.text, "lxml")

                    item_sel = ac.get("item_selector", "article, .news-item, .list-item, li, tr")
                    for el in soup.select(item_sel):
                        if len(items) >= max_items:
                            break

                        title_el = el if el.name == "a" and el.get("href") else el.select_one(
                            "a[href], h2 a, h3 a, .title a, h1, h2, h3, .title")
                        title = title_el.get_text(strip=True) if title_el else ""
                        if not title or len(title) < 4:
                            continue

                        link_el = el if el.name == "a" and el.get("href") else el.select_one("a[href]")
                        href = link_el.get("href", "") if link_el else ""
                        if href and not href.startswith("http"):
                            href = urljoin(cfg.base_url, href)

                        title_include = ac.get("title_include_pattern")
                        if title_include and not re.search(title_include, title):
                            continue

                        title_exclude = ac.get("title_exclude_pattern")
                        if title_exclude and re.search(title_exclude, title):
                            continue

                        href_include = ac.get("href_include_pattern")
                        if href_include and not re.search(href_include, href or ""):
                            continue

                        href_exclude = ac.get("href_exclude_pattern")
                        if href_exclude and re.search(href_exclude, href or ""):
                            continue

                        if href in seen:
                            continue
                        seen.add(href)

                        date_el = el.select_one("time, .date, .pub-date, span.date, [datetime]")
                        published = None
                        if date_el:
                            dt_text = date_el.get("datetime", "") or date_el.get_text(strip=True)
                            published = _parse_date(dt_text)
                        if not published:
                            published = _parse_date(el.get_text(" ", strip=True))
                        if not published and el.name == "a" and el.parent:
                            published = _parse_date(el.parent.get_text(" ", strip=True))

                        content = ""
                        summary = ""
                        if (
                            href
                            and ac.get("fetch_detail", True)
                            and _same_origin(cfg.base_url, href)
                        ):
                            try:
                                detail_resp = await fetch_public_html(
                                    client, href, timeout_seconds=cfg.timeout_seconds,
                                    minimum_interval_seconds=_minimum_request_interval(cfg),
                                )
                                if detail_resp is None:
                                    raise ValueError("详情页未通过公网 HTML 安全校验")
                                extracted = extract_article_text(
                                    detail_resp.text, detail_resp.url,
                                )
                                content = extracted.get("content", "")
                                summary = extracted.get("summary", "")
                                if not published and extracted.get("published_at"):
                                    published = _parse_date(extracted["published_at"])
                                await asyncio.sleep(
                                    1.0 / cfg.rate_limit_rps if cfg.rate_limit_rps else 1.0)
                            except Exception as exc:
                                logger.warning("Detail fetch failed for %s: %s", href[:80], exc)

                        if not ac.get("allow_unfiltered_keywords") and not _matches(title, content, keywords):
                            continue

                        items.append(FetchItem(
                            title=title, content=content, url=href,
                            summary=summary or (content[:500] if content else title[:500]),
                            published_at=published,
                            language=detect_lang(f"{title} {content}"),
                            category=infer_category(title, content),
                            suggested_tags=build_tags(title, content),
                            quality_score=0.7,
                            relevance_score=0.6,
                            raw_metadata={"source_url": href or cfg.base_url},
                        ))

                    await asyncio.sleep(
                        1.0 / cfg.rate_limit_rps if cfg.rate_limit_rps else 1.0)

                except Exception as exc:
                    msg = f"{url[:60]}: {exc}"
                    errors.append(msg)
                    logger.error("Web scrape error for source %s url %s: %s",
                                 self.config.id, url[:80], exc)

        status = JobStatus.COMPLETED if not errors else JobStatus.PARTIAL
        if not items and errors:
            status = JobStatus.FAILED

        logger.info("WebScrape: %d items, %d errors for source %s",
                     len(items), len(errors), self.config.id)
        return CollectResult(
            run_id=self._new_run_id(), source_id=cfg.id,
            status=status, items=items, items_new=len(items),
            items_failed=len(errors), error_log=errors if errors else None,
        )

    def _error(self, msg: str) -> CollectResult:
        return CollectResult(
            run_id=self._new_run_id(), source_id=self.config.id,
            status=JobStatus.FAILED, items=[], error_log=[msg],
        )


# ── helpers ──────────────────────────────────────────────────────────────────

def _scrape_headers() -> dict:
    return {
        "User-Agent": "GatherInfo/0.3 (Global Monitor; contact@example.com)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    }


def _minimum_request_interval(config: SourceConfig) -> float:
    rate_interval = 1.0 / config.rate_limit_rps if config.rate_limit_rps else 1.0
    return max(float(getattr(config, "crawl_delay_seconds", 0) or 0), rate_interval)


def _same_origin(left: str, right: str) -> bool:
    try:
        first = urlsplit(left)
        second = urlsplit(right)
        first_port = first.port or (443 if first.scheme.casefold() == "https" else 80)
        second_port = second.port or (443 if second.scheme.casefold() == "https" else 80)
    except ValueError:
        return False
    return (
        first.scheme.casefold(), (first.hostname or "").casefold(), first_port,
    ) == (
        second.scheme.casefold(), (second.hostname or "").casefold(), second_port,
    )


def _build_urls(base: str, max_pages: int) -> list[str]:
    urls = [base]
    for i in range(2, max_pages + 1):
        urls.append(f"{base.rstrip('/')}/page/{i}")
        urls.append(f"{base.rstrip('/')}?page={i}")
    return urls


def _matches(title: str, content: str, keywords: list[str]) -> bool:
    if not keywords:
        return True
    text = f"{title} {content}".lower()
    return any(kw.lower() in text for kw in keywords)


_CN_PATTERNS = [
    (r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", None),
    (r"(\d{4})年(\d{1,2})月(\d{1,2})日", None),
]


def _parse_date(text: str) -> str | None:
    if not text:
        return None
    patterns = [
        r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})",
        r"(\d{4})年\s*(\d{1,2})月\s*(\d{1,2})日",
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            try:
                parts = [int(x) for x in m.groups()]
                return datetime(parts[0], parts[1], parts[2], tzinfo=timezone.utc).isoformat()
            except ValueError:
                pass
    return None
