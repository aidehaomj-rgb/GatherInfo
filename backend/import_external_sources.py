"""Import 251 external information sources from Excel into source_configs.

Hierarchy design (stored in default_categories as 2-level group path):
  Level 1 (platform):   网页·执法信息 / 网页·热点信息 / 社交媒体·微信公众号 / 社交媒体·微博 / 社交媒体·今日头条
  Level 2 (category):   政府官网 / 新闻媒体 / 专业类网站  (web only)

Dedup by normalized base_url; skips sources already present.
Run:  cd backend && .venv/bin/python import_external_sources.py
"""
from __future__ import annotations
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import openpyxl
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import SourceConfig

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "gather.db"
XLSX_PATH = Path("/Users/m4max/Documents/008-工作文件/外部信息源总表（总251个网站）.xlsx")


def _slug(text: str, max_len: int = 50) -> str:
    s = unicodedata.normalize("NFKC", text or "").strip().lower()
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"[^a-z0-9-]", "", s)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    return s[:max_len] or "src"


def _domain(url: str) -> str:
    try:
        net = urlparse(url).netloc
        return net or ""
    except Exception:
        return ""


def _make_id(name: str, seq: int, seen: set[str]) -> str:
    base = _slug(name)
    for _ in range(20):
        cand = f"ext-{base}-{seq:03d}" if base else f"ext-src-{seq:03d}"
        if cand not in seen:
            seen.add(cand)
            return cand
        seq += 1
    cand = f"ext-{datetime.now(timezone.utc).strftime('%H%M%S')}-{seq}"
    seen.add(cand)
    return cand


def _build_web_source(row, group_l1: str, seq: int, seen: set[str]) -> dict | None:
    """row = (序号, 提出部门, 信息源分类, 国家, 语种, 中文名, 英文名, 频道名, URL, 备注, None)"""
    _, _, cat, country, lang, name_cn, name_en, channel_name, url, remark, _ = row
    if not url or not str(url).startswith("http"):
        return None
    name = str(name_cn or name_en or "").strip()
    if not name:
        return None
    full_name = name
    if channel_name and str(channel_name).strip():
        full_name = f"{name} · {str(channel_name).strip()}"
    desc_parts: list[str] = []
    if channel_name:
        desc_parts.append(f"频道: {channel_name}")
    if lang:
        desc_parts.append(f"语种: {lang}")
    if country:
        desc_parts.append(f"地区: {country}")
    if remark:
        desc_parts.append(f"备注: {remark}")
    return {
        "id": _make_id(name, seq, seen),
        "name": full_name[:200],
        "description": " | ".join(desc_parts)[:500] or None,
        "channel": "web_scrape",
        "is_active": True,
        "base_url": str(url).strip(),
        "homepage_url": f"https://{_domain(url)}" if _domain(url) else None,
       "default_keywords": None,
       "default_categories": [group_l1, str(cat or "其他").strip()] if cat else [group_l1],
       "languages": [str(lang).strip()] if lang else None,
       "country_focus": [str(country).strip()] if country else None,
       "rate_limit_rps": 0.5,
        "is_configured": True,
       "legal_basis": "公开政府/新闻信息",
    }


def _build_social_source(row, group_l1: str, seq: int, seen: set[str], kind: str) -> dict | None:
    if kind == "wechat":
        _, _, account_name, wechat_id = row
        name = str(account_name or "").strip()
        if not name:
            return None
        return {
            "id": _make_id(name, seq, seen),
            "name": name[:200],
           "description": f"微信号: {wechat_id}" if wechat_id else None,
           "channel": "social",
           "is_active": True,
           "base_url": None,
           "default_categories": [group_l1],
           "default_keywords": None,
           "rate_limit_rps": 0.5,
            "is_configured": True,
           "legal_basis": "公开社交媒体信息",
        }
    if kind == "weibo":
        _, username, url, _ = row
        name = str(username or "").strip()
        if not name:
            return None
        return {
            "id": _make_id(name, seq, seen),
            "name": name[:200],
           "description": None,
           "channel": "social",
           "is_active": True,
           "base_url": str(url).strip() if url and str(url).startswith("http") else None,
           "default_categories": [group_l1],
           "default_keywords": None,
           "rate_limit_rps": 0.5,
            "is_configured": True,
           "legal_basis": "公开社交媒体信息",
        }
    if kind == "toutiao":
        _, _cat, account_name = row
        name = str(account_name or "").strip()
        if not name:
            return None
        return {
            "id": _make_id(name, seq, seen),
            "name": name[:200],
           "description": "今日头条APP 媒体账号",
           "channel": "social",
           "is_active": True,
           "base_url": None,
           "default_categories": [group_l1],
           "default_keywords": None,
           "rate_limit_rps": 0.5,
            "is_configured": True,
           "legal_basis": "公开社交媒体信息",
        }
    return None


def main() -> None:
    wb = openpyxl.load_workbook(str(XLSX_PATH), data_only=True)
    engine = create_engine(f"sqlite:///{DB_PATH}")
    sources: list[dict] = []
    seen_ids: set[str] = set()
    seq = 1

    # 1. 网页-执法信息
    ws = wb["网页-执法信息"]
    for row in ws.iter_rows(min_row=2, values_only=True):
        src = _build_web_source(row, "网页·执法信息", seq, seen_ids)
        if src:
            sources.append(src)
            seq += 1

    # 2. 网页-热点信息
    ws = wb["网页-热点信息"]
    for row in ws.iter_rows(min_row=2, values_only=True):
        src = _build_web_source(row, "网页·热点信息", seq, seen_ids)
        if src:
            sources.append(src)
            seq += 1

    # 3. 微信公众号
    ws = wb["微信公众号-热点信息"]
    for row in ws.iter_rows(min_row=2, values_only=True):
        src = _build_social_source(row, "社交媒体·微信公众号", seq, seen_ids, "wechat")
        if src:
            sources.append(src)
            seq += 1

    # 4. 微博
    ws = wb["微博--热点信息"]
    for row in ws.iter_rows(min_row=2, values_only=True):
        src = _build_social_source(row, "社交媒体·微博", seq, seen_ids, "weibo")
        if src:
            sources.append(src)
            seq += 1

    # 5. 今日头条
    ws = wb["今日头条-媒体账号"]
    for row in ws.iter_rows(min_row=2, values_only=True):
        src = _build_social_source(row, "社交媒体·今日头条", seq, seen_ids, "toutiao")
        if src:
            sources.append(src)
            seq += 1

    print(f"Parsed {len(sources)} sources from Excel")

    with Session(engine) as db:
        existing_urls = {
            s.base_url for s in db.query(SourceConfig).all() if s.base_url
        }
        existing_names = {s.name for s in db.query(SourceConfig).all()}
        created = 0
        skipped = 0
        for cfg in sources:
            if cfg.get("base_url") and cfg["base_url"] in existing_urls:
                skipped += 1
                continue
            if cfg["name"] in existing_names:
                skipped += 1
                continue
            db.add(SourceConfig(**cfg))
            created += 1
        db.commit()
        print(f"Created {created} new sources, skipped {skipped} duplicates")
        total = db.query(SourceConfig).count()
        print(f"Total sources in DB: {total}")


if __name__ == "__main__":
    main()
