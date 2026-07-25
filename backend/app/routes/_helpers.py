"""Shared helpers used across route modules."""
import re
import unicodedata
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models import Category, CollectedItem, SourceConfig, Topic


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_punct(text: str | None) -> str:
    """容错：将中文逗号/冒号归一化为英文，便于后续拆分。"""
    if not text:
        return ""
    return text.replace("，", ",").replace("：", ":")


def _normalize_topic_payload(payload: dict) -> dict:
    """容错：归一化 topic 关键词/标签里残留的中文标点，并按逗号拆分关键词。"""
    kws = payload.get("keywords")
    if isinstance(kws, list):
        normalized: list[str] = []
        for k in kws:
            if isinstance(k, str):
                for part in _normalize_punct(k).split(","):
                    part = part.strip()
                    if part and part not in normalized:
                        normalized.append(part)
            else:
                normalized.append(k)
        payload["keywords"] = normalized
    rules = payload.get("auto_tag_rules")
    if isinstance(rules, list):
        for r in rules:
            if isinstance(r, dict):
                if isinstance(r.get("keyword"), str):
                    r["keyword"] = _normalize_punct(r["keyword"])
                if isinstance(r.get("tag"), str):
                    r["tag"] = _normalize_punct(r["tag"])
    kts = payload.get("keyword_tags")
    if isinstance(kts, list):
        expanded: list = []
        for kt in kts:
            if isinstance(kt, dict) and isinstance(kt.get("keyword"), str):
                parts = [p.strip() for p in _normalize_punct(kt["keyword"]).split(",") if p.strip()]
                if len(parts) <= 1:
                    kt["keyword"] = parts[0] if parts else ""
                    expanded.append(kt)
                else:
                    for part in parts:
                        expanded.append({**kt, "keyword": part})
            else:
                expanded.append(kt)
        payload["keyword_tags"] = expanded
    return payload


def _slugify(text: str, max_len: int = 40) -> str:
    """Generate a URL/ID-friendly slug from arbitrary text (incl. CJK)."""
    if not text:
        return ""
    normalized = unicodedata.normalize("NFKC", text).strip().lower()
    slug = re.sub(r"[\s_]+", "-", normalized)
    slug = re.sub(r"[^a-z0-9-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:max_len]


def _gen_id(name: str, prefix_max: int = 40, exists_fn=None) -> str:
    """Build a unique-ish id from name: slug + short hash; fall back to hash-only."""
    base = _slugify(name, prefix_max)
    suffix = uuid4().hex[:6]
    candidate = f"{base}-{suffix}" if base else f"item-{suffix}"
    if exists_fn:
        while exists_fn(candidate):
            candidate = f"{base}-{uuid4().hex[:6]}" if base else f"item-{uuid4().hex[:6]}"
    return candidate


def _item_tags(item: CollectedItem) -> list[dict]:
    return [{"id": t.id, "namespace": t.namespace, "value": t.value, "label": t.label}
            for t in (item.tags or [])]


def _source_names(db: Session, source_ids) -> list[str]:
    if not source_ids:
        return []
    from app.models import SourceConfig
    rows = db.query(SourceConfig.id, SourceConfig.name).filter(SourceConfig.id.in_(source_ids)).all()
    name_map = {sid: name for sid, name in rows}
    return [name_map.get(sid, sid) for sid in source_ids]


def _category_name(db: Session, cat_id: str | None) -> str | None:
    if not cat_id:
        return None
    cat = db.query(Category).filter(Category.id == cat_id).first()
    return cat.name if cat else None


def _topic_out(db: Session, t: Topic) -> "TopicOut":
    from app.collection_schemas import TopicOut
    out = TopicOut.model_validate(t)
    out.source_names = _source_names(db, t.source_ids)
    out.category_name = _category_name(db, t.category_id)
    return out


# Per-channel default connection metadata
CHANNEL_DEFAULTS: dict[str, dict] = {
    "api_search": {
        "description": "Web 搜索 (Tavily API)",
        "default_base_url": "https://api.tavily.com",
        "default_api_endpoint": "/search",
        "required_fields": ["api_key"],
        "optional_fields": ["base_url", "api_endpoint"],
        "homepage_hint": "https://tavily.com",
    },
    "ai_research": {
        "description": "AI 智能检索（聚合 Tavily 与百度搜索；云端模型配置后可扩展检索词）",
        "default_base_url": "https://api.tavily.com",
        "default_api_endpoint": "/search",
        "required_fields": ["api_key"],
        "optional_fields": ["base_url", "api_endpoint", "auth_config"],
        "homepage_hint": "https://tavily.com",
    },
    "json_api": {
        "description": "通用 JSON API 直连 (NewsAPI / UN Comtrade / World Bank / Inoreader / Feedly 等)",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": ["base_url"],
        "optional_fields": ["api_endpoint", "api_key", "auth_config"],
        "homepage_hint": "https://newsapi.org",
    },
    "rss": {
        "description": "RSS/Atom 订阅源",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": ["base_url"],
        "optional_fields": [],
        "homepage_hint": None,
    },
    "web_scrape": {
        "description": "结构化页面抓取 (CSS 选择器)",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": ["base_url"],
        "optional_fields": ["auth_config"],
        "homepage_hint": None,
    },
    "official": {
        "description": "官方 API (WTO ePing / EUR-Lex / 中国海关 / MOFCOM / UN Comtrade 等)",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": ["base_url"],
        "optional_fields": ["api_key", "auth_config"],
        "homepage_hint": None,
    },
    "commercial": {
        "description": "商业数据 API (Panjiva / ImportGenius / PIERS 等)",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": ["api_key", "base_url"],
        "optional_fields": ["auth_config"],
        "homepage_hint": None,
    },
    "social": {
        "description": "社交媒体采集 (Telegram / Twitter / 特定话题群组)",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": ["base_url"],
        "optional_fields": ["api_key", "auth_config"],
        "homepage_hint": None,
    },
    "deepweb": {
        "description": "深网/暗网采集 (需授权 + 特殊代理)",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": ["base_url"],
        "optional_fields": ["api_key", "auth_config"],
        "homepage_hint": None,
    },
    "manual": {
        "description": "手动录入",
        "default_base_url": "",
        "default_api_endpoint": "",
        "required_fields": [],
        "optional_fields": [],
        "homepage_hint": None,
    },
}

