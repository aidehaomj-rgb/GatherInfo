"""Import source inventory CSV rows without disturbing operational secrets/history."""
from __future__ import annotations

import csv
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

from sqlalchemy.orm import Session

from app._models_enums import SourceChannel
from app.models import SourceConfig
from app.source_taxonomy import determine_source_group


_TRUE_VALUES = frozenset({"1", "true", "yes", "y", "是"})
_TRACKING_PARAMS = frozenset({"gclid", "fbclid", "mc_cid", "mc_eid"})
_LIST_SEPARATOR = re.compile(r"[、,，;；]+")


def normalize_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKC", value or "").casefold()
    return re.sub(r"[\W_]+", "", normalized, flags=re.UNICODE)


def normalize_description(value: str | None) -> str:
    return " ".join((value or "").casefold().split())


def normalize_url(value: str | None) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    try:
        parsed = urlsplit(raw if "://" in raw else f"https://{raw}")
        host = (parsed.hostname or "").casefold().removeprefix("www.")
        port = f":{parsed.port}" if parsed.port and parsed.port not in (80, 443) else ""
        path = re.sub(r"/{2,}", "/", parsed.path or "/").rstrip("/") or "/"
        query = [
            pair for pair in parse_qsl(parsed.query, keep_blank_values=True)
            if not pair[0].casefold().startswith("utm_")
            and pair[0].casefold() not in _TRACKING_PARAMS
        ]
        return urlunsplit(("https", host + port, path, urlencode(sorted(query)), ""))
    except ValueError:
        return raw.casefold().rstrip("/")


def effective_source_urls(source: SourceConfig) -> set[str]:
    urls: set[str] = set()
    base_url = (source.base_url or "").strip()
    endpoint = (source.api_endpoint or "").strip()
    if base_url:
        urls.add(normalize_url(base_url))
    if endpoint:
        resolved = endpoint if endpoint.startswith("http") else urljoin(
            f"{base_url.rstrip('/')}/", endpoint.lstrip("/"),
        )
        urls.add(normalize_url(resolved))
    return urls - {""}


def split_values(value: str | None) -> list[str]:
    return list(dict.fromkeys(
        part.strip() for part in _LIST_SEPARATOR.split(value or "") if part.strip()
    ))


def parse_bool(value: str | None) -> bool:
    return (value or "").strip().casefold() in _TRUE_VALUES


def load_inventory(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        rows = list(reader)
    if not rows:
        return []
    keys = (
        "id", "name", "channel", "collect_url", "homepage_url",
        "default_keywords", "default_categories", "languages",
        "country_focus", "is_active", "is_configured", "allow_llm",
        "health_status", "description",
    )
    if len(rows[0]) != len(keys):
        raise ValueError(f"Expected {len(keys)} columns, got {len(rows[0])}")
    return [dict(zip(keys, row, strict=True)) for row in rows[1:]]


def inventory_payload(row: dict[str, str]) -> dict[str, Any]:
    country_focus = [
        value for value in split_values(row["country_focus"])
        if value.casefold() not in {"待核验", "unknown", "待确认", "n/a"}
    ]
    source: dict[str, Any] = {
        "id": row["id"].strip(),
        "name": row["name"].strip(),
        "description": row["description"].strip() or None,
        "channel": row["channel"].strip().lower().removeprefix("sourcechannel."),
        "is_active": parse_bool(row["is_active"]),
        "is_configured": parse_bool(row["is_configured"]),
        "base_url": row["collect_url"].strip() or None,
        "homepage_url": row["homepage_url"].strip() or None,
        "default_keywords": split_values(row["default_keywords"]) or None,
        "default_categories": split_values(row["default_categories"]) or None,
        "languages": split_values(row["languages"]) or None,
        "country_focus": country_focus or None,
    }
    source["source_group"] = determine_source_group(source)
    return source


def _source_channel(value: str) -> SourceChannel:
    """Convert inventory text to the enum expected by the target ORM."""
    normalized = value.strip().lower().removeprefix("sourcechannel.")
    if normalized == "deep_web":
        normalized = "deepweb"
    try:
        return SourceChannel(normalized)
    except ValueError as exc:
        raise ValueError(f"Unsupported source channel: {value}") from exc


def _merge_values(current: list[str] | None, incoming: list[str] | None) -> list[str] | None:
    combined = list(dict.fromkeys([*(current or []), *(incoming or [])]))
    return combined or None


def _merge_metadata(source: SourceConfig, payload: dict[str, Any]) -> bool:
    changed = False
    for field in ("description", "base_url", "homepage_url"):
        if not getattr(source, field) and payload.get(field):
            setattr(source, field, payload[field])
            changed = True
    for field in ("default_keywords", "default_categories", "languages", "country_focus"):
        merged = _merge_values(getattr(source, field), payload.get(field))
        if merged != getattr(source, field):
            setattr(source, field, merged)
            changed = True
    return changed


def import_source_inventory(db: Session, rows: list[dict[str, str]]) -> dict[str, Any]:
    existing = db.query(SourceConfig).all()
    by_id = {source.id.casefold(): source for source in existing}
    by_name: dict[str, list[SourceConfig]] = defaultdict(list)
    by_url: dict[str, list[SourceConfig]] = defaultdict(list)
    for source in existing:
        by_name[normalize_text(source.name)].append(source)
        for url in effective_source_urls(source):
            by_url[url].append(source)

    result: dict[str, Any] = {
        "incoming": len(rows), "inserted": 0, "merged": 0,
        "matched_unchanged": 0, "skipped_exact_duplicates": 0,
        "conflicts": [],
    }
    used_ids = set(by_id)
    matched_source_ids: set[str] = set()
    for row in rows:
        payload = inventory_payload(row)
        incoming_url = normalize_url(payload.get("base_url"))
        incoming_name = normalize_text(payload["name"])
        source = by_id.get(payload["id"].casefold())
        if source is None and incoming_url:
            # Shared APIs/feeds can intentionally represent multiple configs.
            # Merge a URL match only when the normalized names corroborate that
            # it is the same semantic source.
            url_matches = [
                item for item in by_url[incoming_url]
                if normalize_text(item.name) == incoming_name
            ]
            if len(url_matches) == 1:
                source = url_matches[0]
            elif len(url_matches) > 1:
                result["conflicts"].append({
                    "id": payload["id"],
                    "reason": "ambiguous URL and name",
                    "matching_ids": sorted(item.id for item in url_matches),
                })
                continue
        if source is None and not incoming_url:
            # A name alone is too weak for social/manual sources.  Their
            # account/platform description must also agree.
            name_matches = [
                item for item in by_name[incoming_name]
                if normalize_description(item.description)
                == normalize_description(payload.get("description"))
            ]
            if len(name_matches) == 1:
                source = name_matches[0]
            elif len(name_matches) > 1:
                result["conflicts"].append({
                    "id": payload["id"],
                    "reason": "ambiguous name and description",
                    "matching_ids": sorted(item.id for item in name_matches),
                })
                continue
        if source is not None:
            if source.id in matched_source_ids:
                # Multiple inventory rows may intentionally map to the same
                # semantic source. Still merge any additional non-secret
                # metadata instead of silently discarding later rows.
                if _merge_metadata(source, payload):
                    result["merged"] += 1
                else:
                    result["skipped_exact_duplicates"] += 1
                continue
            matched_source_ids.add(source.id)
            if _merge_metadata(source, payload):
                result["merged"] += 1
            else:
                result["matched_unchanged"] += 1
            continue
        if payload["id"].casefold() in used_ids:
            result["conflicts"].append({"id": payload["id"], "reason": "duplicate id"})
            continue
        payload["channel"] = _source_channel(str(payload["channel"]))
        new_source = SourceConfig(**payload)
        db.add(new_source)
        existing.append(new_source)
        used_ids.add(payload["id"].casefold())
        matched_source_ids.add(payload["id"])
        by_id[payload["id"].casefold()] = new_source
        by_name[normalize_text(payload["name"])].append(new_source)
        if incoming_url:
            by_url[incoming_url].append(new_source)
        result["inserted"] += 1
    db.flush()
    return result
