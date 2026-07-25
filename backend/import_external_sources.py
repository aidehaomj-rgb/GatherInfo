"""Import the external information-source workbook into ``source_configs``.

The workbook contains web pages and social-media accounts. Web pages can be
collected by the existing ``web_scrape`` connector and are enabled on import.
Social accounts are retained as source records but left inactive until a lawful,
supported collection method is configured.

Usage:
    cd backend
    .venv\\Scripts\\python.exe import_external_sources.py --xlsx "C:\\path\\sources.xlsx"
    .venv\\Scripts\\python.exe import_external_sources.py --xlsx "C:\\path\\sources.xlsx" --dry-run
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from collections import Counter
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import openpyxl
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.models import SourceConfig


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "gather.db"
WEB_GROUPS = {
    0: "网页-执法信息",
    1: "网页-热点信息",
}
SOCIAL_GROUPS = {
    2: "社交媒体-微信公众号",
    3: "社交媒体-微博",
    4: "社交媒体-今日头条",
}


def normalise_url(value: object) -> str:
    """Return a stable URL key for duplicate detection."""
    raw = str(value or "").strip()
    if not raw or not raw.lower().startswith(("http://", "https://")):
        return ""
    parsed = urlparse(raw)
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((parsed.scheme.lower(), parsed.netloc.lower(), path, "", parsed.query, ""))


def homepage_url(url: str) -> str | None:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None
    return f"{parsed.scheme}://{parsed.netloc}/"


def make_slug(text: str, seq: int, seen_ids: set[str]) -> str:
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    base = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")[:42] or "source"
    candidate = f"ext-{base}-{seq:03d}"
    suffix = 2
    while candidate in seen_ids:
        candidate = f"ext-{base[:36]}-{seq:03d}-{suffix}"
        suffix += 1
    seen_ids.add(candidate)
    return candidate


def clean(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def build_web_source(row: tuple, group: str, seq: int, seen_ids: set[str]) -> dict | None:
    values = list(row) + [None] * 11
    _, department, category, country, language, name_cn, name_en, channel_name, url, remark, _ = values[:11]
    url = normalise_url(url)
    name = clean(name_cn) or clean(name_en)
    if not name:
        return None

    channel_label = clean(channel_name)
    full_name = f"{name} - {channel_label}" if channel_label else name
    description_parts = []
    for label, value in (("提出部门", department), ("信息源分类", category), ("频道", channel_name), ("备注", remark)):
        if clean(value):
            description_parts.append(f"{label}: {clean(value)}")

    categories = [group]
    if clean(category):
        categories.append(clean(category))
    if not url:
        return {
            "id": make_slug(full_name, seq, seen_ids),
            "name": full_name[:200],
            "description": " | ".join(description_parts)[:1500] or None,
            "channel": "manual",
            "is_active": False,
            "is_configured": False,
            "rate_limit_rps": 0.5,
            "max_items_per_run": 50,
            "default_categories": categories,
            "languages": [clean(language)] if clean(language) else None,
            "country_focus": [clean(country)] if clean(country) else None,
            "legal_basis": "公开互联网信息",
            "compliance_note": "原始信息源总表未提供可用 URL，待补充网址并完成连通性验证后启用。",
        }
    return {
        "id": make_slug(full_name, seq, seen_ids),
        "name": full_name[:200],
        "description": " | ".join(description_parts)[:1500] or None,
        "channel": "web_scrape",
        "is_active": True,
        "is_configured": True,
        "base_url": url,
        "homepage_url": homepage_url(url),
        "rate_limit_rps": 0.5,
        "max_items_per_run": 50,
        "default_categories": categories,
        "languages": [clean(language)] if clean(language) else None,
        "country_focus": [clean(country)] if clean(country) else None,
        "legal_basis": "公开互联网信息",
        "compliance_note": "仅采集公开网页信息，遵守来源网站使用规则、robots 协议和访问频率限制。",
    }


def build_social_source(row: tuple, group: str, sheet_index: int, seq: int, seen_ids: set[str]) -> dict | None:
    values = list(row) + [None] * 4
    if sheet_index == 2:
        _, department, account_name, account_id = values[:4]
        url = None
        detail = f"微信号: {clean(account_id)}" if clean(account_id) else None
    elif sheet_index == 3:
        department, account_name, source_url, _ = values[:4]
        url = normalise_url(source_url) or None
        detail = None
    else:
        _, department, account_name, _ = values[:4]
        url = None
        detail = "今日头条媒体账号"

    name = clean(account_name)
    if not name:
        return None
    description_parts = [part for part in (f"提出部门: {clean(department)}" if clean(department) else None, detail) if part]
    return {
        "id": make_slug(name, seq, seen_ids),
        "name": name[:200],
        "description": " | ".join(description_parts) or None,
        "channel": "manual",
        "is_active": False,
        "is_configured": False,
        "base_url": url,
        "homepage_url": homepage_url(url) if url else None,
        "rate_limit_rps": 0.5,
        "max_items_per_run": 50,
        "default_categories": [group],
        "legal_basis": "公开社交媒体信息",
        "compliance_note": "待依法合规配置可用接口或人工订阅方式后启用；当前不自动采集。",
    }


def parse_workbook(xlsx_path: Path) -> tuple[list[dict], Counter]:
    workbook = openpyxl.load_workbook(xlsx_path, data_only=True, read_only=True)
    sources: list[dict] = []
    counts: Counter = Counter()
    seen_ids: set[str] = set()
    seq = 1

    for index, worksheet in enumerate(workbook.worksheets):
        group = WEB_GROUPS.get(index) or SOCIAL_GROUPS.get(index)
        if not group:
            continue
        for row in worksheet.iter_rows(min_row=2, values_only=True):
            source = (
                build_web_source(row, group, seq, seen_ids)
                if index in WEB_GROUPS
                else build_social_source(row, group, index, seq, seen_ids)
            )
            if not source:
                counts[f"{group}:invalid"] += 1
                continue
            sources.append(source)
            counts[group] += 1
            seq += 1
    return sources, counts


def import_sources(sources: list[dict], db_path: Path, dry_run: bool) -> Counter:
    engine = create_engine(f"sqlite:///{db_path}")
    results: Counter = Counter()
    with Session(engine) as db:
        existing = db.query(SourceConfig).all()
        seen_urls = {normalise_url(item.base_url) for item in existing if normalise_url(item.base_url)}
        seen_names = {item.name.strip().casefold() for item in existing if item.name}

        for source in sources:
            url = normalise_url(source.get("base_url"))
            name = source["name"].strip().casefold()
            if (url and url in seen_urls) or name in seen_names:
                results["skipped_duplicate"] += 1
                continue
            if not dry_run:
                db.add(SourceConfig(**source))
            seen_urls.add(url) if url else None
            seen_names.add(name)
            results["created"] += 1
            results[f"created_{source['channel']}"] += 1
        if not dry_run:
            db.commit()
        results["total_after"] = db.query(SourceConfig).count() + (results["created"] if dry_run else 0)
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Import an external information-source workbook.")
    parser.add_argument("--xlsx", required=True, type=Path, help="Path to the source workbook")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH, help="SQLite database path")
    parser.add_argument("--dry-run", action="store_true", help="Validate and count without writing")
    args = parser.parse_args()

    if not args.xlsx.is_file():
        raise SystemExit(f"Workbook not found: {args.xlsx}")
    if not args.db.is_file():
        raise SystemExit(f"Database not found: {args.db}")

    sources, parsed = parse_workbook(args.xlsx)
    result = import_sources(sources, args.db, args.dry_run)
    print(f"Parsed {len(sources)} valid sources: {dict(parsed)}")
    print(f"Import result ({'dry run' if args.dry_run else 'written'}): {dict(result)}")


if __name__ == "__main__":
    main()
