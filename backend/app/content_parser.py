"""Local content quality checks and lightweight structure extraction."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from app.connectors.base import FetchItem

# ── Noise tokens ─────────────────────────────────────────────────────────────
NOISE_TOKENS = {
    "首页", "登录", "注册", "版权", "菜单", "导航", "更多", "返回", "搜索",
    "home", "login", "register", "copyright", "menu", "navigation",
    "subscribe", "cookie", "privacy", "terms", "breadcrumb", "sitemap",
}

# ── Navigation keywords (expanded) ───────────────────────────────────────────
NAV_KEYWORDS = {
    # Chinese
    "首页", "新闻中心", "国家媒体发布", "跳至正文内容", "跳至主要内容",
    "统计数据和摘要", "问责制和透明度", "媒体发布", "文件库", "新闻官员",
    "社交媒体目录", "多媒体图书馆", "法律声明", "前线数字杂志", "新闻通讯",
    "公告", "出版物目录", "聚光灯", "关于我们", "联系我们", "网站地图",
    "无障碍访问", "隐私政策", "使用条款", "快速链接", "常见问题",
    "有用链接", "面包屑", "breadcrumb",
    # English
    "skip to main content", "skip to content", "skip navigation",
    "contact us", "about us", "sitemap", "accessibility", "foia",
    "privacy policy", "terms of use", "terms of service", "cookie policy",
    "quick links", "frequently asked questions", "faq", "useful links",
    "news center", "press releases", "media library", "social media",
    "official statements", "publications", "spotlight", "newsletter",
    "announcements", "breadcrumb", "search", "menu", "navigation",
    "home", "login", "register", "subscribe", "share", "print",
    "follow us", "connect with us", "related links", "resources",
    "download", "pdf", "doc", "excel", "powerpoint", "slides",
    "read more", "learn more", "click here", "view all", "see all",
    "back to top", "top of page", "previous", "next", "page ",
    "january", "february", "march", "april", "may", "june",
    "july", "august", "september", "october", "november", "december",
    "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    # Government / agency site chrome (navigation, boilerplate, footer)
    "travel", "border security", "border patrol", "careers", "employee resources",
    "newsroom", "media releases", "accountability", "transparency",
    "stats and summaries", "documents library", "publications catalog",
    "about cbp", "who we are", "learn about", "mobile apps", "mobile apps directory",
    "congressional resources", "biometrics", "trusted traveler", "visa waiver",
    "global entry", "nexus", "sentri", "fast", "general aviation", "international visitors",
    "media contacts", "office of public affairs", "information center",
    "social media directory", "youtube channel", "video", "multimedia libraries",
    "legal notices", "site policies", "freedom of information", "no fear",
    "vulnerability disclosure", "the white house", "usa.gov", "dhs components",
    "section 508", "inspector general", "comunicados de prensa",
    "freedom 250", "office of trade", "office of field operations",
    "air and marine operations", "ports of entry", "cargo security",
    "career paths", "applicant categories", "benefits", "retirement",
    "work-life balance", "new employee resources", "email updates", "social icons",
    "official website of the united states government", "official websites use",
    "secure .gov websites use https", "here's how you know",
    "share sensitive information only on official",
    "selected to participate in a brief survey", "survey about your experience",
}

# ── Markdown / boilerplate noise stripping ───────────────────────────────────
# ![alt](url) — image alt text and URLs are pure navigation/decorative noise
_MD_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\([^)]*\)")
# []() — empty anchor (decorative)
_MD_EMPTY_LINK_PATTERN = re.compile(r"\[\]\([^)]*\)")
# Numeric breadcrumb trail: "1 [Home](url) 2 [Newsroom](url) 3 [Title]"
_NUMERIC_BREADCRUMB_PATTERN = re.compile(r"(?:\d{1,2}\s*\[[^\]]*\]\([^)]*\)\s*){2,}")
# Markdown link [text](url) — keep anchor text, drop the URL
_MD_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\([^)]*\)")
# Markdown bold/italic markers left behind after link stripping
_MD_EMPHASIS_PATTERN = re.compile(r"\*{1,3}|_{1,3}")
# Markdown heading markers (### Title) — at line start or inline after list text
_MD_HEADING_PATTERN = re.compile(r"(?:^|\s)#{1,6}\s+")

# Government/agency site boilerplate — deterministic chrome to strip outright.
# Case-insensitive substring match; order from longest to shortest.
BOILERPLATE_PHRASES = [
    # English (.gov banner + survey invite)
    "share sensitive information only on official, secure websites",
    "a .gov website belongs to an official government organization",
    "an official website of the united states government",
    "you have been selected to participate in a brief survey about your experience today",
    "official websites use .gov",
    "secure .gov websites use https",
    "here's how you know",
    "a lock or https means you've safely connected",
    # Chinese (.gov banner)
    "仅在官方安全网站上共享敏感信息",
    ".gov 网站属于美国的官方政府组织",
    "官方网站使用 .gov",
    "安全 .gov 网站使用 HTTPS",
    "你是这样知道的",
    "官方网站美国政府的信息",
]


def _strip_boilerplate(text: str) -> str:
    """Remove known government-site banner/footer boilerplate.

    Whitespace-insensitive so bold-marker splitting (``**A** **.gov**``) doesn't
    defeat the match.
    """
    for phrase in BOILERPLATE_PHRASES:
        pattern = re.compile(
            r"\s+".join(re.escape(part) for part in phrase.split()),
            re.IGNORECASE,
        )
        text = pattern.sub(" ", text)
    return text


def _strip_links(text: str) -> str:
    """Convert markdown links to anchor text, dropping pure-navigation links.

    A link whose anchor is a short navigation keyword (e.g. ``[Travel](url)``,
    ``[Section 508](url)``) is dropped entirely; a meaningful inline link
    (``[Centers of Excellence and Expertise](url)``) keeps its anchor text.
    """
    def _replacer(match: re.Match) -> str:
        anchor = match.group(1)
        anchor_clean = _MD_EMPHASIS_PATTERN.sub(" ", anchor).strip()
        words = re.findall(r"[\w\u4e00-\u9fff]+", anchor_clean.lower())
        if words and len(anchor_clean) <= 40:
            nav_hits = sum(1 for word in words if word in NAV_KEYWORDS)
            if nav_hits / len(words) >= 0.5:
                return " "
        return anchor
    return _MD_LINK_PATTERN.sub(_replacer, text)

# ── Patterns ─────────────────────────────────────────────────────────────────
BREADCRUMB_PATTERN = re.compile(
    r"(?:\b(?:首页|home|主页|Home)\b)\s*[>›/→|\\-]\s*[^\n]{0,80}(?:\s*[>›/→|\\-]\s*[^\n]{0,80})*",
    re.IGNORECASE,
)

SKIP_NAV_PATTERN = re.compile(
    r"skip\s+to\s+(?:main\s+)?content\s*[\n\s]*",
    re.IGNORECASE,
)

# Lines that are clearly navigation (short + contain nav words)
NAV_LINE_PATTERN = re.compile(
    r"^\s*(?:\d{1,2}\s+)?(?:"
    r"home|login|register|menu|navigation|search|about|contact|"
    r"sitemap|privacy|terms|cookie|subscribe|share|follow|"
    r"首页|登录|注册|关于|联系|搜索|菜单|导航|更多|返回"
    r")\s*$",
    re.IGNORECASE,
)

COUNTRY_PATTERNS = {
    "United States": ("United States", "U.S.", "US ", "USA", "美国"),
    "China": ("China", "Chinese", "中国", "中方"),
    "European Union": ("European Union", "EU ", "欧盟"),
    "Japan": ("Japan", "日本"),
    "Canada": ("Canada", "加拿大"),
    "Mexico": ("Mexico", "墨西哥"),
}


@dataclass(frozen=True)
class ParsedContent:
    content: str
    summary: str
    entities: dict[str, Any]
    metadata: dict[str, Any]
    is_meaningful: bool


def parse_fetch_item(item: FetchItem) -> ParsedContent:
    """Normalize content and extract enough structure for local persistence."""
    title = _normalize_text(item.title)
    raw_content = item.content or item.summary or ""
    content = _normalize_text(raw_content)
    summary = _normalize_text(item.summary or "")

    # If summary is just a truncated version of content or contains nav, regenerate
    if not summary or _is_nav_heavy(summary) or (content and summary in content[:len(summary)+10]):
        summary = _make_summary(content or title)

    combined = " ".join(part for part in (title, summary, content) if part)
    substantive_tokens = _substantive_tokens(combined)
    is_meaningful = _is_meaningful(title, content, substantive_tokens)
    entities = _merge_entities(item.entities, _extract_entities(combined))
    metadata = _merge_metadata(item.raw_metadata, combined, substantive_tokens)
    return ParsedContent(
        content=content,
        summary=summary,
        entities=entities,
        metadata=metadata,
        is_meaningful=is_meaningful,
    )


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    cleaned = re.sub(r"<[^>]+>", " ", str(value))
    cleaned = re.sub(r"[\x00-\x1f\x7f]+", " ", cleaned)

    # 0. Strip markdown/boilerplate noise before any other processing:
    #    images, empty links, breadcrumb trails, then inline links → anchor text.
    cleaned = _MD_IMAGE_PATTERN.sub(" ", cleaned)
    cleaned = _MD_EMPTY_LINK_PATTERN.sub(" ", cleaned)
    cleaned = _NUMERIC_BREADCRUMB_PATTERN.sub(" ", cleaned)
    cleaned = _strip_links(cleaned)
    cleaned = _MD_EMPHASIS_PATTERN.sub(" ", cleaned)
    cleaned = _MD_HEADING_PATTERN.sub(" ", cleaned)
    cleaned = _strip_boilerplate(cleaned)

    # 1. Remove skip links and breadcrumb patterns
    cleaned = SKIP_NAV_PATTERN.sub(" ", cleaned)
    cleaned = BREADCRUMB_PATTERN.sub(" ", cleaned)

    # 2. Split into paragraphs and filter
    paragraphs = re.split(r"\n\s*\n|\n", cleaned)
    filtered_paragraphs: list[str] = []
    seen_counts: dict[str, int] = {}

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        # Skip very short lines that look like navigation
        if len(para) <= 30 and NAV_LINE_PATTERN.match(para):
            continue

        # Skip paragraphs that are mostly navigation keywords
        para_lower = para.lower()
        words = re.findall(r"[\w\u4e00-\u9fff]+", para_lower)
        if words:
            nav_hits = sum(1 for w in words if w in NAV_KEYWORDS)
            if nav_hits / len(words) > 0.25:
                continue

        # Skip lines that are just lists of nav items (each line short)
        lines = [line.strip() for line in para.split("\n") if line.strip()]
        if lines and all(len(line) <= 25 for line in lines):
            nav_line_hits = sum(
                1 for line in lines
                if any(kw in line.lower() for kw in NAV_KEYWORDS)
            )
            if nav_line_hits / len(lines) > 0.40:
                continue

        # Skip repeated content (like "News Center" appearing many times)
        para_key = re.sub(r"\s+", " ", para_lower)
        seen_counts[para_key] = seen_counts.get(para_key, 0) + 1
        if seen_counts[para_key] > 2:
            continue

        # Skip paragraphs that are just date lists or month names
        if _is_date_list(para):
            continue

        filtered_paragraphs.append(para)

    cleaned = "\n\n".join(filtered_paragraphs)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def _is_date_list(text: str) -> bool:
    """Check if text is just a list of dates/months (common in nav sidebars)."""
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    if not lines or len(lines) < 2:
        return False
    month_pattern = re.compile(
        r"^(?:january|february|march|april|may|june|july|august|"
        r"september|october|november|december|"
        r"\d{4}|\d{1,2}/\d{1,2}/\d{2,4})\s*$",
        re.IGNORECASE,
    )
    date_lines = sum(1 for line in lines if month_pattern.match(line))
    return date_lines / len(lines) > 0.5


def _is_nav_heavy(text: str) -> bool:
    """Check if text is dominated by navigation content."""
    if not text:
        return False
    words = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    if not words:
        return False
    nav_hits = sum(1 for w in words if w in NAV_KEYWORDS)
    return nav_hits / len(words) > 0.20


def _make_summary(text: str, limit: int = 300) -> str:
    """Generate a meaningful summary from content."""
    if not text:
        return ""
    if len(text) <= limit:
        return text

    # Try to find a sentence boundary
    sentence_end = re.search(r'[.!?。！？]\s+(?=[A-Z"\u4e00-\u9fff])', text[:limit+50])
    if sentence_end and sentence_end.end() > limit * 0.5:
        return text[:sentence_end.end()].strip()

    # Fallback: break at last space before limit
    return text[:limit].rsplit(" ", 1)[0].strip() + "..."


def _substantive_tokens(text: str) -> list[str]:
    raw_tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())
    return [token for token in raw_tokens if token and token not in NOISE_TOKENS]


def _is_meaningful(title: str, content: str, tokens: list[str]) -> bool:
    if not title and not content:
        return False
    title_tokens = _substantive_tokens(title)
    has_meaningful_title = any(len(token) >= 3 for token in title_tokens)
    if has_meaningful_title:
        return True
    if len(tokens) >= 3:
        return True
    cjk_chars = re.findall(r"[\u4e00-\u9fff]", f"{title}{content}")
    return len(cjk_chars) >= 8 and len(tokens) >= 2


def _extract_entities(text: str) -> dict[str, Any]:
    countries = [
        name for name, patterns in COUNTRY_PATTERNS.items()
        if any(pattern in text for pattern in patterns)
    ]
    years = sorted(set(re.findall(r"\b(?:19|20)\d{2}\b", text)))
    numbers = re.findall(r"\b\d+(?:\.\d+)?%?\b", text)[:20]
    return {
        "countries": countries,
        "years": years,
        "numbers": numbers,
    }


def _merge_entities(existing: dict | None, extracted: dict[str, Any]) -> dict[str, Any]:
    base = existing if isinstance(existing, dict) else {}
    return {
        **base,
        "countries": list(dict.fromkeys([*(base.get("countries") or []), *extracted["countries"]])),
        "years": list(dict.fromkeys([*(base.get("years") or []), *extracted["years"]])),
        "numbers": list(dict.fromkeys([*(base.get("numbers") or []), *extracted["numbers"]])),
    }


def _merge_metadata(
    existing: dict | None, text: str, tokens: list[str],
) -> dict[str, Any]:
    base = existing if isinstance(existing, dict) else {}
    return {
        **base,
        "content_analysis": {
            "char_count": len(text),
            "word_count": len(tokens),
            "unique_word_count": len(set(tokens)),
        },
    }
