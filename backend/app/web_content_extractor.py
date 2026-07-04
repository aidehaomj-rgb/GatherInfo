"""Smart article content extraction from HTML.

Uses a density-based algorithm to find the main article body,
similar to readability algorithms. Falls back to CSS selectors.
"""
from __future__ import annotations

import re
from typing import Any

from bs4 import BeautifulSoup, Tag


def extract_article_text(html: str, url: str = "") -> dict[str, Any]:
    """Extract article title, content, and metadata from HTML.

    Returns dict with: title, content, summary, author, published_at, word_count
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove noise elements first
    _remove_noise(soup)

    # Extract title
    title = _extract_title(soup)

    # Try to find main article body
    article_body = _find_article_body(soup)

    if article_body:
        content = _extract_text_from_element(article_body)
    else:
        # Fallback: use body but with aggressive filtering
        body = soup.find("body")
        content = _extract_text_from_element(body) if body else ""

    # Clean up the content
    content = _clean_extracted_content(content)

    # Extract metadata
    published_at = _extract_published_date(soup)
    author = _extract_author(soup)

    # Generate summary from first meaningful paragraph
    summary = _generate_summary(content)

    word_count = len(re.findall(r"[\w\u4e00-\u9fff]+", content))

    return {
        "title": title,
        "content": content,
        "summary": summary,
        "author": author,
        "published_at": published_at,
        "word_count": word_count,
    }


def _remove_noise(soup: BeautifulSoup) -> None:
    """Remove navigation, ads, sidebars, and other non-content elements."""
    selectors = [
        # Navigation
        "nav", ".nav", ".navbar", ".navigation", ".menu", ".main-menu",
        ".skip-link", "[role='navigation']", ".breadcrumb", ".breadcrumbs",
        # Header elements that aren't the article header
        "header:not(.article-header):not(.entry-header)",
        # Sidebars and widgets
        ".sidebar", ".widget", ".widgets", "aside", ".aside",
        # Footer
        "footer", ".footer", ".site-footer",
        # Ads and social
        ".ad", ".ads", ".advertisement", ".social-share", ".share-buttons",
        ".follow-us", ".newsletter", ".subscribe",
        # Comments and related
        ".comments", ".comment-section", ".related-posts", ".related-articles",
        # Scripts and styles
        "script", "style", "noscript", "iframe",
        # Common nav patterns
        ".top-bar", ".top-nav", ".bottom-nav", ".pagination",
        ".search-box", ".search-form", ".site-search",
        # TOC and meta
        ".toc", ".table-of-contents", ".meta", ".post-meta",
        # Cookie banners
        ".cookie-banner", ".cookie-consent", ".gdpr",
    ]

    for selector in selectors:
        try:
            for el in soup.select(selector):
                el.decompose()
        except Exception:
            pass

    # Also remove elements with common nav-related IDs/classes
    nav_patterns = re.compile(
        r"nav|menu|header|footer|sidebar|widget|ad-|banner|cookie|gdpr|"
        r"search|breadcrumb|share|social|subscribe|newsletter|comment|"
        r"related|pagination|toc|meta-|skip|accessibility",
        re.IGNORECASE,
    )

    # Structural tags that should never be removed even if class matches nav patterns
    _structural_tags = {"html", "head", "body", "main", "article"}
    for el in soup.find_all(True):
        if not isinstance(el, Tag):
            continue
        if el.name in _structural_tags:
            continue
        try:
            el_id = el.get("id") or ""
            el_class = " ".join(el.get("class") or [])
        except (AttributeError, TypeError):
            continue
        # Skip layout classes like "layout-one-sidebar" that aren't actual sidebars
        if el_class and "layout" in el_class.lower():
            continue
        if nav_patterns.search(el_id) or nav_patterns.search(el_class):
            # Don't remove if it's inside an article body
            if not _is_inside_article(el):
                el.decompose()


def _is_inside_article(el: Tag) -> bool:
    """Check if element is inside an article or main content area."""
    parent = el.parent
    while parent and isinstance(parent, Tag):
        tag_name = parent.name or ""
        parent_class = " ".join(parent.get("class") or [])
        if tag_name in ("article", "main") or "article" in parent_class or "content" in parent_class:
            return True
        parent = parent.parent
    return False


def _find_article_body(soup: BeautifulSoup) -> Tag | None:
    """Find the main article body using multiple strategies."""

    # Strategy 1: Common article selectors
    article_selectors = [
        "article",
        "[role='main']",
        "main",
        ".article-content",
        ".entry-content",
        ".post-content",
        ".content-body",
        ".story-body",
        ".news-body",
        "#content-main",
        ".main-content",
        ".page-content",
        ".body-content",
    ]

    for selector in article_selectors:
        el = soup.select_one(selector)
        if el and _has_substantial_text(el):
            return el

    # Strategy 2: Density-based scoring
    candidates = _score_elements(soup)
    if candidates:
        return candidates[0][0]

    return None


def _score_elements(soup: BeautifulSoup) -> list[tuple[Tag, float]]:
    """Score elements by text density to find the article body."""
    scores: list[tuple[Tag, float]] = []

    for el in soup.find_all(["div", "section", "article", "main"]):
        if not isinstance(el, Tag):
            continue

        text = el.get_text(strip=True)
        text_len = len(text)

        # Skip very small or very large elements
        if text_len < 200 or text_len > 50000:
            continue

        # Calculate text density (text length / tag count)
        tag_count = len(el.find_all(True))
        if tag_count == 0:
            continue

        density = text_len / tag_count

        # Bonus for article-like classes
        el_class = " ".join(el.get("class", []))
        bonus = 0
        if any(kw in el_class for kw in ["article", "content", "entry", "post", "story", "news", "body"]):
            bonus = 50

        # Penalty for nav-like classes
        penalty = 0
        if any(kw in el_class for kw in ["nav", "menu", "sidebar", "widget", "footer", "header"]):
            penalty = 100

        score = density + bonus - penalty

        # Must have substantial paragraphs
        paragraphs = el.find_all("p")
        if len(paragraphs) >= 2:
            scores.append((el, score))

    scores.sort(key=lambda x: x[1], reverse=True)
    return scores[:5]


def _has_substantial_text(el: Tag, min_chars: int = 500) -> bool:
    """Check if element has substantial text content."""
    text = el.get_text(strip=True)
    return len(text) >= min_chars


def _extract_text_from_element(el: Tag | None) -> str:
    """Extract clean text from an element, preserving paragraph structure."""
    if not el:
        return ""

    # Get all paragraph-like elements
    paragraphs: list[str] = []

    # First try to get <p> tags
    p_tags = el.find_all("p")
    if p_tags:
        for p in p_tags:
            text = p.get_text(strip=True)
            if text and len(text) > 10:
                paragraphs.append(text)

    # If no <p> tags found, get text from all block-level elements
    if not paragraphs:
        for block in el.find_all(["div", "section", "article", "li"]):
            text = block.get_text(strip=True)
            if text and len(text) > 20:
                paragraphs.append(text)

    # If still nothing, get all text
    if not paragraphs:
        text = el.get_text(separator="\n", strip=True)
        paragraphs = [line.strip() for line in text.split("\n") if line.strip() and len(line.strip()) > 20]

    return "\n\n".join(paragraphs)


def _extract_title(soup: BeautifulSoup) -> str:
    """Extract article title from HTML."""
    # Try h1 first
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)
        if title and len(title) > 5:
            return title

    # Try article title classes
    for selector in [".article-title", ".entry-title", ".post-title", ".headline", ".title"]:
        el = soup.select_one(selector)
        if el:
            title = el.get_text(strip=True)
            if title and len(title) > 5:
                return title

    # Fallback to <title> tag
    title_tag = soup.find("title")
    if title_tag:
        title = title_tag.get_text(strip=True)
        # Clean up common suffixes
        title = re.sub(r"\s*[\-|–—]\s*.*$", "", title)
        return title

    return ""


def _extract_published_date(soup: BeautifulSoup) -> str | None:
    """Extract published date from HTML meta tags."""
    # Try common meta tags
    meta_selectors = [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"property": "og:published_time"}),
        ("meta", {"name": "publishedDate"}),
        ("meta", {"name": "date"}),
        ("meta", {"name": "DC.date.issued"}),
        ("time", {"class": re.compile(r"date|published|time")}),
    ]

    for tag, attrs in meta_selectors:
        el = soup.find(tag, attrs)
        if el:
            date_str = el.get("content") or el.get_text(strip=True)
            if date_str:
                return date_str

    return None


def _extract_author(soup: BeautifulSoup) -> str | None:
    """Extract author from HTML meta tags."""
    meta_selectors = [
        ("meta", {"name": "author"}),
        ("meta", {"property": "article:author"}),
        ("a", {"class": re.compile(r"author")}),
        ("span", {"class": re.compile(r"author")}),
    ]

    for tag, attrs in meta_selectors:
        el = soup.find(tag, attrs)
        if el:
            author = el.get("content") or el.get_text(strip=True)
            if author:
                return author

    return None


def _clean_extracted_content(text: str) -> str:
    """Clean extracted content: remove navigation remnants, normalize whitespace."""
    if not text:
        return ""

    # Remove common navigation remnants
    nav_patterns = [
        r"Skip\s+to\s+(?:main\s+)?content\s*",
        r"跳至(?:正文|主要)?内容\s*",
        r"Breadcrumb\s*",
        r"面包屑\s*",
        r"Quick\s+links\s*",
        r"快速链接\s*",
        r"Frequently\s+asked\s+questions\s*",
        r"常见问题\s*",
        r"Useful\s+links\s*",
        r"有用链接\s*",
        r"Search\s*",
        r"搜索\s*",
    ]

    for pattern in nav_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)

    # Normalize whitespace
    text = re.sub(r"\n\s*\n\s*\n+", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n ", "\n", text)
    text = re.sub(r" \n", "\n", text)

    return text.strip()


def _generate_summary(content: str, max_len: int = 400) -> str:
    """Generate a summary from the first meaningful paragraph."""
    if not content:
        return ""

    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

    for para in paragraphs:
        # Skip very short paragraphs
        if len(para) < 30:
            continue
        # Skip paragraphs that look like navigation
        if _is_nav_text(para):
            continue

        if len(para) <= max_len:
            return para
        # Find sentence boundary
        sentence_end = re.search(r'[.!?。！？]\s+(?=[A-Z"\u4e00-\u9fff])', para[:max_len+50])
        if sentence_end and sentence_end.end() > max_len * 0.3:
            return para[:sentence_end.end()].strip()
        return para[:max_len].rsplit(" ", 1)[0].strip() + "..."

    return ""


def _is_nav_text(text: str) -> bool:
    """Check if text is navigation-like."""
    nav_words = {
        "home", "login", "register", "menu", "navigation", "search",
        "about", "contact", "sitemap", "privacy", "terms", "cookie",
        "首页", "登录", "注册", "关于", "联系", "搜索", "菜单", "导航",
    }
    words = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    if not words:
        return False
    nav_count = sum(1 for w in words if w in nav_words)
    return nav_count / len(words) > 0.3
