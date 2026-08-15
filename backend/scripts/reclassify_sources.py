"""Normalize source categories into a business-friendly taxonomy.

Run from the project root:
    backend\.venv\Scripts\python.exe backend\scripts\reclassify_sources.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.database import SessionLocal
from app.models import SourceConfig


PRIMARY_ORDER = {
    "official-policy": "官方政策法规",
    "customs-enforcement": "海关执法查发",
    "export-control-sanctions": "出口管制与制裁",
    "tbt-sps-regulation": "技术性贸易措施",
    "critical-minerals-commodities": "关键矿产与大宗商品",
    "trade-remedy-tariff": "关税税则与贸易救济",
    "search-ai": "搜索与AI检索",
    "commercial-data": "商业/API数据",
    "news-enforcement": "新闻媒体-执法线索",
    "news-hotspots": "新闻媒体-时政热点",
    "social-osint": "社交媒体/公众号",
    "manual-standby": "备用未配置",
    "uncategorized": "其他未分类",
}

SUBTYPE_LABELS = {
    "official": "官方来源",
    "international": "国际组织",
    "government": "政府官网",
    "customs": "海关/边境机构",
    "enforcement": "执法查发",
    "export-control": "出口管制",
    "sanctions": "制裁合规",
    "tbt-sps": "TBT/SPS",
    "critical-minerals": "关键矿产",
    "commodity": "商品价格/行业数据",
    "tariff": "关税税则",
    "trade-remedy": "贸易救济",
    "search-api": "搜索API",
    "ai-research": "AI智能检索",
    "data-api": "数据API",
    "rss": "RSS订阅",
    "media": "新闻媒体",
    "public-account": "公众号/社媒",
    "manual": "手工维护",
}


def _cats(source: SourceConfig) -> list[str]:
    value = source.default_categories
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [value]
        return [str(item) for item in parsed if str(item).strip()] if isinstance(parsed, list) else []
    return []


def classify(source: SourceConfig) -> list[str]:
    sid = source.id.lower()
    name = (source.name or "").lower()
    channel = str(source.channel or "").lower()
    raw_cats = _cats(source)
    if raw_cats and raw_cats[0] in PRIMARY_ORDER and raw_cats[0] != "uncategorized":
        return raw_cats[:2] if len(raw_cats) >= 2 else [raw_cats[0], "manual"]

    cats = [cat.lower() for cat in raw_cats]
    text = " ".join([sid, name, channel, *cats])

    if "ai_research" in channel or "ai智能检索" in text or "ai smart" in text:
        return ["search-ai", "ai-research"]
    if "search" in channel or any(token in sid for token in ("tavily", "baidu", "bing", "search1api", "google-alerts")):
        return ["search-ai", "search-api"]
    if channel in {"json_api", "commercial"} or any(token in sid for token in ("newsapi", "inoreader", "rss-app", "comtrade", "worldbank")):
        return ["commercial-data", "data-api"]
    if channel == "manual" or not source.is_configured:
        if "社交媒体" in text or "公众号" in text or "微博" in text or "今日头条" in text:
            return ["social-osint", "public-account"]
        return ["manual-standby", "manual"]

    if any(token in text for token in ("网页-执法信息", "执法信息", "enforcement", "customs", "border", "cbp", "wco", "海关", "关务", "border force")):
        if any(token in text for token in ("rss", "官方", "government", "customs", "wco", "cbp", "mofcom", "海关总署")):
            return ["customs-enforcement", "customs"]
        return ["news-enforcement", "media"]

    if any(token in text for token in ("export_control", "export-control", "出口管制", "sanction", "ofac", "bis", "制裁")):
        subtype = "sanctions" if any(token in text for token in ("sanction", "ofac", "制裁")) else "export-control"
        return ["export-control-sanctions", subtype]

    if any(token in text for token in ("tbt_sps", "tbt", "sps", "eping", "技术性贸易措施")):
        return ["tbt-sps-regulation", "tbt-sps"]

    if any(token in text for token in ("critical-minerals", "mineral", "usgs", "稀土", "矿产", "commodity", "price", "fao", "iea", "imf-commodity")):
        subtype = "critical-minerals" if any(token in text for token in ("critical", "mineral", "usgs", "稀土", "矿产")) else "commodity"
        return ["critical-minerals-commodities", subtype]

    if any(token in text for token in ("tariff", "trade_remedy", "反倾销", "反补贴", "关税", "usitc")):
        subtype = "trade-remedy" if "trade_remedy" in text or "usitc" in text else "tariff"
        return ["trade-remedy-tariff", subtype]

    if any(token in text for token in ("trade", "policy", "regulation", "fta", "wto", "ustr", "mofcom", "商务部", "eurlex", "un-news", "unctad", "asean", "oecd")):
        if any(token in text for token in ("wto", "wco", "un-", "unctad", "asean", "oecd", "eurlex", "eaeu")):
            return ["official-policy", "international"]
        return ["official-policy", "official"]

    if "网页-热点信息" in text or "涉进出口时政热点" in text or "新闻媒体" in text:
        return ["news-hotspots", "media"]

    if sid.startswith("ext-") and _numeric_tail(sid) >= 127:
        if any(token in text for token in ("商务部", "大使馆", "农业农村部", "国家药品监督管理局", "国家税务总局", "美国国际贸易管理局", "欧盟理事会")):
            return ["official-policy", "government"]
        if any(token in text for token in ("贸易救济", "tariff", "tariffs")):
            return ["trade-remedy-tariff", "trade-remedy"]
        if any(token in text for token in ("矿业", "矿产", "金属", "稀土", "argusmetals", "smm")):
            return ["critical-minerals-commodities", "critical-minerals"]
        return ["news-hotspots", "media"]

    if "weekly-eu-council" in sid:
        return ["official-policy", "international"]

    return ["uncategorized", "manual"]


def _numeric_tail(value: str) -> int:
    digits = "".join(ch for ch in value if ch.isdigit())
    return int(digits) if digits else 0


def main() -> None:
    db = SessionLocal()
    try:
        rows = db.query(SourceConfig).all()
        changed = 0
        for source in rows:
            new_categories = classify(source)
            if _cats(source) != new_categories:
                source.default_categories = new_categories
                changed += 1
        db.commit()
        print(f"reclassified={changed} total={len(rows)}")
        summary: dict[str, int] = {}
        for source in rows:
            primary = _cats(source)[0] if _cats(source) else "uncategorized"
            summary[primary] = summary.get(primary, 0) + 1
        for key in PRIMARY_ORDER:
            if key in summary:
                print(f"{PRIMARY_ORDER[key]}: {summary[key]}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
