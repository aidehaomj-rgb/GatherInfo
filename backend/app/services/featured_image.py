"""重点信息配图解析服务。

为「情报主页」的重点信息解析一张真实、主题相关的配图：
1. 从信息源头页面（item.url）抓取 og:image / twitter:image / 正文大图；
2. 下载到本地 data/featured_images/ 目录，通过 /static/featured-images 静态挂载返回；
3. 源头无图或抓取失败时，从 Wikimedia Commons 按标题关键词搜一张主题相关图兜底。

设计原则：失败静默降级（返回 None），绝不阻塞首页渲染。
"""
from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from app.database import DATA_DIR
from app.models import CollectedItem

logger = logging.getLogger(__name__)

# 使用与数据库一致的绝对 data 目录，避免进程 cwd 不同导致图片散落多处
FEATURED_IMAGE_DIR = Path(DATA_DIR) / "featured_images"
STATIC_PREFIX = "/static/featured-images"
MAX_CANDIDATES = 6
TIMEOUT = 8.0

_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

# 图片 URL 命中这些词则视为装饰性图标/logo，跳过
_DECORATIVE_HINTS = (
    "logo", "icon", "flag", "avatar", "seal", "sprite", "close",
    "search", "banner-small", "us_flag", "cbp-logo", "dhs-logo",
    "social-icons", "usa-icons", "email.svg", "x20.svg",
)

_CONTENT_TYPE_EXT = {
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


def _http_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": _USER_AGENT},
        timeout=TIMEOUT,
        follow_redirects=True,
    )


def _image_filename(item_id: str, url: str, content_type: str | None) -> str:
    digest = hashlib.sha256(f"{item_id}:{url}".encode("utf-8")).hexdigest()[:16]
    ext = _CONTENT_TYPE_EXT.get((content_type or "").split(";")[0].strip(), ".jpg")
    return f"{digest}{ext}"


def _is_http_url(url: str) -> bool:
    return url.startswith("http://") or url.startswith("https://")


def _extract_source_images(html: str, base_url: str) -> list[str]:
    """Extract candidate image URLs from a page: og:image first, then body images."""
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []

    # 1) Open Graph / Twitter meta image（最高优先，通常是事件主图）
    for meta in soup.find_all("meta"):
        prop = (meta.get("property") or meta.get("name") or "").lower()
        if prop in ("og:image", "og:image:url", "og:image:secure_url",
                    "twitter:image", "twitter:image:src"):
            content = meta.get("content")
            if content:
                candidates.append(urljoin(base_url, content.strip()))

    # 2) 正文 <img>，跳过明显装饰性图
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src:
            continue
        width = img.get("width")
        if width and str(width).isdigit() and int(width) < 120:
            continue
        full = urljoin(base_url, src.strip())
        if _is_http_url(full) and not any(h in full.lower() for h in _DECORATIVE_HINTS):
            candidates.append(full)

    # 去重并保序
    seen: list[str] = []
    for url in candidates:
        if url not in seen:
            seen.append(url)
    return seen


def _download_image(client: httpx.Client, item_id: str, url: str) -> str | None:
    """Download an image to the local featured-images dir; return static URL."""
    try:
        resp = client.get(url)
        resp.raise_for_status()
    except Exception:
        return None

    content_type = resp.headers.get("content-type", "")
    if not content_type.lower().startswith("image/"):
        return None
    if len(resp.content) < 1024:  # 忽略极小/占位图
        return None

    FEATURED_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    filename = _image_filename(item_id, url, content_type)
    dest = FEATURED_IMAGE_DIR / filename
    dest.write_bytes(resp.content)
    return f"{STATIC_PREFIX}/{filename}"


def _extract_search_keywords(item: CollectedItem) -> str:
    """Derive a short English keyword phrase for fallback image search."""
    title = (item.title or "").strip()
    if not title:
        return "international trade"
    # 取标题前 6 个有意义的英文词作为搜索词，避免长句
    words = re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", title)
    keywords = " ".join(words[:6]).strip()
    return keywords or "international trade"


def _wikimedia_search_image(client: httpx.Client, keyword: str) -> str | None:
    """Fallback: search a topical image from Wikimedia Commons (no API key)."""
    try:
        params = {
            "action": "query",
            "generator": "search",
            "gsrsearch": f"filetype:bitmap {keyword}",
            "gsrlimit": 5,
            "gsrnamespace": 6,  # File namespace
            "prop": "imageinfo",
            "iiprop": "url|size",
            "iiurlwidth": 1200,
            "format": "json",
        }
        resp = client.get("https://commons.wikimedia.org/w/api.php", params=params)
        resp.raise_for_status()
        data = resp.json()
        pages = (data.get("query") or {}).get("pages") or {}
        for page in pages.values():
            info = (page.get("imageinfo") or [{}])[0]
            thumb = info.get("thumburl") or info.get("url")
            if thumb and _is_http_url(thumb):
                return thumb
    except Exception:
        return None
    return None


def resolve_featured_image(db: Session, item: CollectedItem) -> str | None:
    """Resolve and persist a featured image URL for one item.

    Returns the static local URL on success, else None. Never raises.
    """
    if item.featured_image_url:
        return item.featured_image_url

    try:
        with _http_client() as client:
            # 1) 源头页面抓图
            if item.url and _is_http_url(item.url):
                try:
                    html = client.get(item.url).text
                except Exception:
                    html = ""
                for candidate in _extract_source_images(html, item.url)[:MAX_CANDIDATES]:
                    local = _download_image(client, item.id, candidate)
                    if local:
                        item.featured_image_url = local
                        db.commit()
                        return local

            # 2) Wikimedia 兜底搜图（主题相关）
            keyword = _extract_search_keywords(item)
            remote = _wikimedia_search_image(client, keyword)
            if remote:
                local = _download_image(client, item.id, remote)
                if local:
                    item.featured_image_url = local
                    db.commit()
                    return local
    except Exception as exc:
        logger.warning("featured image resolve failed for %s: %s", item.id, exc)

    return None


def resolve_featured_images(db: Session, items: list[CollectedItem]) -> dict[str, str | None]:
    """Resolve featured images for a batch of items; returns {item_id: url | None}."""
    result: dict[str, str | None] = {}
    for item in items:
        result[item.id] = resolve_featured_image(db, item)
    return result
