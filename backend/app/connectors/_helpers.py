"""Shared helpers for connector modules — DRY across search_engines, web_scrape, etc."""
import re

from app.connectors.base import CollectResult, FetchItem, JobStatus


def result(run_id: str, source_id: str, items: list[FetchItem], errors: list[str]) -> CollectResult:
    """Build a CollectResult with appropriate status based on items/errors."""
    st = JobStatus.COMPLETED
    if not items and errors:
        st = JobStatus.FAILED
    elif errors:
        st = JobStatus.PARTIAL
    return CollectResult(
        run_id=run_id, source_id=source_id, status=st,
        items=items, items_new=len(items), items_failed=len(errors),
        error_log=errors if errors else None,
    )


def detect_lang(text: str) -> str:
    """Best-effort language detection for the built-in multilingual search paths."""
    if len(re.findall(r'[\u0900-\u097f]', text[:500])) > 3:
        return "hi"
    if len(re.findall(r'[\u3040-\u30ff]', text[:500])) > 3:
        return "ja"
    cjk = len(re.findall(r'[一-鿿]', text[:500]))
    return "zh" if cjk > 3 else "en"


def infer_category(title: str, content: str) -> str | None:
    """Infer a category label from title + content keywords."""
    text = f"{title} {content}"[:500].lower()
    for kws, cat in [
        (["关税", "tariff", "税率", "duty"], "tariff"),
        (["法规", "regulation", "政策", "law"], "regulation"),
        (["贸易", "trade", "export", "进口", "出口"], "trade"),
        (["技术", "technology", "ai", "芯片", "半导体"], "technology"),
        (["能源", "energy", "oil", "solar", "光伏"], "energy"),
        (["制裁", "sanction", "管制", "control"], "security"),
    ]:
        if any(k in text for k in kws):
            return cat
    return "general"


def build_tags(title: str, content: str) -> list[str]:
    """Build suggested tags from title + content keyword matching."""
    text = f"{title} {content}"[:1000].lower()
    tags = []
    tag_map = {
        "product:battery": ["电池", "battery", "锂电"],
        "product:solar": ["光伏", "solar"],
        "product:semiconductor": ["芯片", "半导体", "semiconductor"],
        "product:ev": ["电动汽车", "新能源车", "电动"],
        "product:steel": ["钢", "steel"],
        "country:cn": ["中国", "china"],
        "country:us": ["美国", "united states"],
        "country:eu": ["欧盟", "european union"],
        "event:tariff": ["关税", "tariff", "税率"],
        "event:regulation": ["法规", "regulation", "政策"],
        "event:sanction": ["制裁", "sanction"],
    }
    for tid, kws in tag_map.items():
        if any(k in text for k in kws):
            tags.append(tid)
    return tags[:8]


def extract_title(soup) -> str:
    """Extract page title from BeautifulSoup."""
    for sel in ["h1", "title", "meta[property='og:title']", ".article-title"]:
        el = soup.select_one(sel)
        if el:
            return el.get("content", "") or el.get_text(strip=True)
    return ""


def extract_body(soup, content_sel: str) -> str:
    """Extract body text from BeautifulSoup with selector."""
    for tag in soup.select("script, style, nav, footer, .ad, .sidebar"):
        tag.decompose()
    el = soup.select_one(content_sel) if content_sel else None
    if el:
        return el.get_text(separator="\n", strip=True)[:5000]
    return soup.get_text(separator="\n", strip=True)[:5000]
