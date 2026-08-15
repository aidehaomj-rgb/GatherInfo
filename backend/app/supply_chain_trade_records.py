from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

from app.research_document_reader import read_document


PUBLIC_TRADE_INDEX_COUNTRIES = {"United States"}

CHINA_ORIGIN_LABELS = {
    "china", "mainland china", "people's republic of china", "pr china", "prc",
}


def _normalized(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u0900-\u097f\u3040-\u30ff\u3400-\u9fff]+", "", str(value or "").casefold())


def _date(value: str) -> datetime | None:
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _looks_like_bill_number(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9./_-]{5,}", value.strip()))


def _source_country(source: dict[str, Any], countries: list[str]) -> str | None:
    hint = str(source.get("country_hint") or "")
    if hint in countries:
        return hint
    host = urlparse(str(source.get("url") or "")).netloc.casefold()
    return "United States" if "United States" in countries and host.endswith("importgenius.com") else None


def _table_rows(
    source: dict[str, Any], country: str, *, cutoff: datetime, as_of: datetime,
) -> list[dict[str, Any]]:
    text = str(source.get("content") or "")
    title = str(source.get("title") or "")
    host = urlparse(str(source.get("url") or "")).netloc.casefold()
    if host.endswith("importgenius.com") and "see full importer history" not in title.casefold():
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    records: list[dict[str, Any]] = []
    for index, raw_date in enumerate(lines):
        parsed = _date(raw_date)
        if not parsed or index < 4 or index + 1 >= len(lines):
            continue
        origin = lines[index + 1].casefold().strip()
        bill_no, product, importer, exporter = lines[index - 4:index]
        if origin not in CHINA_ORIGIN_LABELS or not _looks_like_bill_number(bill_no):
            continue
        if not (cutoff <= parsed <= as_of + timedelta(days=1)):
            continue
        if exporter.casefold() in {"n/a", "unknown", "supplier"}:
            continue
        excerpt = (
            f"提单号 {bill_no}；进口商 {importer}；中国出口商 {exporter}；"
            f"货物 {product}；到港日期 {raw_date}；原产国 {lines[index + 1]}"
        )
        records = [*records, {
            "country": country,
            "importer_name": importer.rstrip(","),
            "exporter_name": exporter.rstrip(","),
            "product": product[:500],
            "contract_title": None,
            "contract_evidence_url": None,
            "trade_evidence_url": source.get("url"),
            "trade_reference": bill_no,
            "trade_date": parsed.date().isoformat(),
            "trade_date_basis": "shipment_record",
            "trade_excerpt": excerpt,
            "supporting_urls": [],
            "confidence_score": 72,
            "limitations": ["贸易记录仅证明该企业近期自中国进口，不能单独证明该批货物进入具体军工项目。"],
            "deterministic_extraction": True,
            "trade_source_kind": "public_trade_index_table",
        }]
    return records


def _collapse_importer_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in sorted(records, key=lambda row: str(row.get("trade_date") or ""), reverse=True):
        key = (str(item.get("country") or ""), _normalized(item.get("importer_name")))
        grouped = {**grouped, key: [*(grouped.get(key) or []), item]}
    collapsed = []
    for values in grouped.values():
        primary = values[0]
        related = [
            {
                "trade_reference": item.get("trade_reference"),
                "trade_date": item.get("trade_date"),
                "exporter_name": item.get("exporter_name"),
                "product": item.get("product"),
            }
            for item in values[:6]
        ]
        collapsed = [*collapsed, {**primary, "related_trade_records": related}]
    return collapsed


def extract_structured_trade_records(
    sources: list[dict[str, Any]], countries: list[str], *,
    as_of: datetime, import_record_window_days: int,
) -> list[dict[str, Any]]:
    normalized_as_of = as_of.astimezone(timezone.utc)
    cutoff = normalized_as_of - timedelta(days=import_record_window_days)
    records = []
    for source in sources:
        country = _source_country(source, countries)
        if not country:
            continue
        records = [
            *records,
            *_table_rows(source, country, cutoff=cutoff, as_of=normalized_as_of),
        ]
    return _collapse_importer_records(records)


def merge_source_records(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for source in sources:
        url = str(source.get("url") or "")
        if not url:
            continue
        current = merged.get(url) or {}
        non_empty = {key: value for key, value in source.items() if value not in (None, "", [])}
        merged = {**merged, url: {**current, **non_empty}}
    return list(merged.values())


def build_public_trade_index_probes(
    countries: list[str], targets: list[dict[str, Any]], *, max_probes: int = 12,
) -> list[tuple[str, str, str]]:
    """Build importer-profile probes from entities found during this research run."""
    allowed_countries = set(countries) & PUBLIC_TRADE_INDEX_COUNTRIES
    probes: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    for target in targets:
        country = str(target.get("country") or "")
        name = str(target.get("company_name") or "").strip()
        if (
            country not in allowed_countries
            or target.get("role") != "defense_importer"
            or not name
        ):
            continue
        key = (country, _normalized(name))
        slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-")
        if not key[1] or key in seen or len(slug) < 3:
            continue
        probes = [*probes, (country, name, slug)]
        seen = {*seen, key}
        if len(probes) >= max_probes:
            break
    return probes


async def probe_public_trade_indexes(
    countries: list[str], targets: list[dict[str, Any]], *,
    as_of: datetime, import_record_window_days: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    specs = build_public_trade_index_probes(countries, targets)
    semaphore = asyncio.Semaphore(4)

    async def probe(country: str, expected_name: str, slug: str) -> tuple[dict[str, Any] | None, str | None]:
        url = f"https://www.importgenius.com/importers/{slug}"
        try:
            async with semaphore:
                document = await read_document(url)
            source = {
                "country_hint": country,
                "mode": "trade_index",
                "title": document.get("title") or expected_name,
                "url": url,
                "summary": f"{expected_name} 公开进口商记录",
                "content": str(document.get("text") or document.get("content") or "")[:16000],
                "search_engine": "direct_trade_index",
                "search_query": f"public importer profile: {expected_name}",
                "language": "en",
            }
            records = extract_structured_trade_records(
                [source], countries, as_of=as_of,
                import_record_window_days=import_record_window_days,
            )
            if not records:
                return None, None
            if not any(
                _normalized(expected_name) in _normalized(item.get("importer_name"))
                or _normalized(item.get("importer_name")) in _normalized(expected_name)
                for item in records
            ):
                return None, None
            return source, None
        except Exception as exc:
            return None, f"trade_index/{expected_name}: {type(exc).__name__}: {exc}"

    responses = await asyncio.gather(*(probe(*spec) for spec in specs))
    sources = [source for source, _ in responses if source]
    errors = [error for _, error in responses if error]
    return sources, errors


def trade_record_targets(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "country": item["country"],
            "company_name": item["importer_name"],
            "aliases": [],
            "role": "defense_importer",
            "address": "",
            "products": [item["product"]],
            "contract_refs": [],
            "trade_counterparties": [item["exporter_name"]],
            "source_urls": [item["trade_evidence_url"]],
            "deterministic_trade_record": True,
        }
        for item in records
    ]


def _same_importer(left: dict[str, Any], right: dict[str, Any]) -> bool:
    if left.get("country") != right.get("country"):
        return False
    left_name = _normalized(left.get("importer_name"))
    right_name = _normalized(right.get("importer_name"))
    return bool(
        left_name and right_name
        and (left_name == right_name or min(len(left_name), len(right_name)) >= 8
             and (left_name in right_name or right_name in left_name))
    )


def _merge_limitations(left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    caveat = "现有公开证据只完成企业层交叉，尚不能证明该具体批次已进入具体军工项目。"
    values = [
        *[str(item) for item in left.get("limitations") or [] if item],
        *[str(item) for item in right.get("limitations") or [] if item],
        caveat,
    ]
    return list(dict.fromkeys(values))


def _merge_pair(base: dict[str, Any], trade: dict[str, Any]) -> dict[str, Any]:
    contract_url = base.get("contract_evidence_url") or trade.get("contract_evidence_url")
    trade_url = base.get("trade_evidence_url") or trade.get("trade_evidence_url")
    if base.get("trade_evidence_url"):
        return {
            **base,
            "related_trade_records": trade.get("related_trade_records") or base.get("related_trade_records") or [],
            "supporting_urls": list(dict.fromkeys([
                *(base.get("supporting_urls") or []), *(trade.get("supporting_urls") or []),
            ])),
        }
    validation = {
        "contract": (base.get("evidence_validation") or {}).get("contract")
                    or (trade.get("evidence_validation") or {}).get("contract") or {"valid": False},
        "trade": (trade.get("evidence_validation") or {}).get("trade")
                 or (base.get("evidence_validation") or {}).get("trade") or {"valid": False},
    }
    closed = bool(contract_url and trade_url)
    return {
        **base,
        "exporter_name": trade.get("exporter_name") or base.get("exporter_name"),
        "exporter_aliases": trade.get("exporter_aliases") or base.get("exporter_aliases") or [],
        "product": trade.get("product") or base.get("product"),
        "trade_evidence_url": trade_url,
        "trade_reference": trade.get("trade_reference") or base.get("trade_reference"),
        "trade_date": trade.get("trade_date") or base.get("trade_date"),
        "trade_date_basis": trade.get("trade_date_basis") or base.get("trade_date_basis"),
        "trade_excerpt": trade.get("trade_excerpt") or base.get("trade_excerpt"),
        "related_trade_records": trade.get("related_trade_records") or [],
        "deterministic_extraction": bool(trade.get("deterministic_extraction")),
        "trade_source_kind": trade.get("trade_source_kind"),
        "confidence_score": max(
            int(base.get("confidence_score") or 0),
            int(trade.get("confidence_score") or 0),
            80 if closed else 0,
        ),
        "evidence_validation": validation,
        "evidence_status": "closed" if closed else "trade_only",
        "evidence_gap": "" if closed else "待补军工合同、采购项目或最终用途证据",
        "limitations": _merge_limitations(base, trade),
        "supporting_urls": list(dict.fromkeys([
            *(base.get("supporting_urls") or []), *(trade.get("supporting_urls") or []),
        ])),
    }


def merge_candidate_evidence(
    model_candidates: list[dict[str, Any]], trade_candidates: list[dict[str, Any]], *, limit: int,
) -> list[dict[str, Any]]:
    rows = [dict(item) for item in model_candidates]
    for trade in trade_candidates:
        match_index = next((index for index, item in enumerate(rows) if _same_importer(item, trade)), None)
        rows = (
            [*rows, dict(trade)]
            if match_index is None
            else [
                _merge_pair(item, trade) if index == match_index else item
                for index, item in enumerate(rows)
            ]
        )
    status_rank = {"closed": 0, "trade_only": 1, "contract_only": 2}
    ranked = sorted(rows, key=lambda item: (
        status_rank.get(str(item.get("evidence_status") or ""), 3),
        -int(item.get("confidence_score") or 0),
    ))
    return ranked[:limit]
