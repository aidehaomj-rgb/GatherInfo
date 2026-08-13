"""Entity extraction and evidence-led follow-up planning for enforcement cases."""
from __future__ import annotations

import re
import json
from collections import Counter
from typing import Any
from urllib.parse import urlparse

from app.llm_client import call_llm
from app.models import CollectedItem, ModelConfig

ENTITY_PATTERNS = {
    "container_numbers": r"\b[A-Z]{4}\s?\d{7}\b",
    "imo_numbers": r"\bIMO\s*[:#-]?\s*\d{7}\b",
    "flight_numbers": r"\b[A-Z]{2,3}[ -]?\d{2,4}\b",
    "case_numbers": r"\b(?:case|docket|file|reference|ref)\s*(?:no\.?|number|#|:)\s*[A-Z0-9][A-Z0-9./-]{3,}\b",
    "bill_numbers": r"\b(?:B/L|BL|bill of lading|waybill)\s*(?:no\.?|#|:)\s*[A-Z0-9-]{5,}\b",
}
COMPANY_SUFFIXES = (
    "Ltd", "Limited", "LLC", "Inc", "Corporation", "Corp", "Company", "Co.",
    "GmbH", "S.A.", "S.A", "Pte Ltd", "Pty Ltd", "集团", "公司", "有限公司",
)
NON_FLIGHT_CODES = {"USD", "EUR", "GBP", "CNY", "RMB", "JPY", "KRW", "AUD", "CAD", "HKD", "NIS", "ILS"}


def enrich_case_entities(item: CollectedItem) -> dict[str, Any]:
    text = "\n".join(str(value or "") for value in (item.title, item.summary, item.content))
    current = dict(item.entities or {})
    for key, pattern in ENTITY_PATTERNS.items():
        flags = 0 if key == "flight_numbers" else re.I
        values = [re.sub(r"\s+", "", value) if key == "container_numbers" else value.strip()
                  for value in re.findall(pattern, text, flags=flags)]
        if key == "flight_numbers":
            values = [value for value in values if re.match(r"[A-Z]{2,3}", value).group(0) not in NON_FLIGHT_CODES]
        current[key] = _unique(values)[:30]
    companies: list[str] = []
    company_pattern = rf"\b(?:[A-Z][\w&'.,-]+[ \t]+){{0,6}}(?:{'|'.join(re.escape(x) for x in COMPANY_SUFFIXES)})\b"
    for line in text.splitlines():
        companies.extend(re.findall(company_pattern, line))
    current["companies"] = _unique([*(current.get("companies") or []), *companies])[:30]
    review = (item.raw_metadata or {}).get("enforcement_review") or {}
    for key in ("subject", "authority", "jurisdiction"):
        value = str(review.get(key) or "").strip()
        if value:
            current[key] = value
    item.entities = current
    metadata = dict(item.raw_metadata or {})
    metadata["entity_research"] = {
        "status": "extracted",
        "entity_count": sum(len(value) for value in current.values() if isinstance(value, list)),
        "cross_source_status": "pending",
        "external_match_status": "not_configured",
    }
    item.raw_metadata = metadata
    return current


async def enrich_entities_with_llm(item: CollectedItem, model: ModelConfig | None) -> dict[str, Any]:
    entities = enrich_case_entities(item)
    if not model or not model.is_active:
        return entities
    prompt = """Extract only entities explicitly present in this enforcement-case source. Return strict JSON with arrays:
companies, people, vessels, flights, container_numbers, case_numbers, bill_numbers, ports, routes, goods, identifiers, aliases.
Do not infer missing names. Keep exact source spelling. TEXT:\n""" + "\n".join(str(v or "") for v in (item.title, item.summary, item.content))[:18000]
    try:
        result = await call_llm(model, prompt, max_tokens_override=1800, timeout_seconds=90)
        extracted = _parse_json_object(result.get("content", ""))
    except Exception:
        extracted = {}
    for key, values in extracted.items():
        if isinstance(values, list):
            entities[key] = _unique([*(entities.get(key) or []), *(str(v) for v in values)])[:40]
    item.entities = entities
    metadata = dict(item.raw_metadata or {})
    metadata["entity_research"] = {**(metadata.get("entity_research") or {}), "llm_status": "completed" if extracted else "unavailable"}
    item.raw_metadata = metadata
    return entities


def update_cross_source_verification(items: list[CollectedItem]) -> None:
    for item in items:
        evidence = []
        item_tokens = _identity_tokens(item)
        for candidate in items:
            if candidate.id == item.id or not candidate.url:
                continue
            if urlparse(candidate.url).netloc.casefold() == urlparse(item.url or "").netloc.casefold():
                continue
            overlap = item_tokens & _identity_tokens(candidate)
            if overlap:
                evidence.append({"item_id": candidate.id, "url": candidate.url, "matched_entities": sorted(overlap)[:8]})
        metadata = dict(item.raw_metadata or {})
        research = dict(metadata.get("entity_research") or {})
        research.update({"cross_source_status": "verified" if evidence else "single_source", "independent_sources": 1 + len(evidence), "corroborating_sources": evidence[:10]})
        metadata["entity_research"] = research
        item.raw_metadata = metadata


def build_gap_followups(items: list[CollectedItem], *, window_start: str, window_end: str) -> list[str]:
    entities = [enrich_case_entities(item) for item in items]
    reviews = [(item.raw_metadata or {}).get("enforcement_review") or {} for item in items]
    jurisdictions = Counter(str(review.get("jurisdiction") or "").strip() for review in reviews)
    china_count = sum(review.get("china_relevance_level") in {"strong", "weak"} for review in reviews)
    queries: list[str] = []
    for entity in entities:
        names = [*(entity.get("companies") or []), entity.get("subject")]
        identifiers = [*(entity.get("container_numbers") or []), *(entity.get("imo_numbers") or []),
                       *(entity.get("case_numbers") or []), *(entity.get("bill_numbers") or [])]
        for value in [*names, *identifiers]:
            value = str(value or "").strip()
            if len(value) >= 4:
                queries.append(f'"{value}" customs seizure arrest China shipment {window_start} {window_end}')
    for item in items:
        research = (item.raw_metadata or {}).get("entity_research") or {}
        if research.get("cross_source_status") != "verified":
            review = (item.raw_metadata or {}).get("enforcement_review") or {}
            subject = str(review.get("subject") or item.title or "").strip()[:160]
            authority = str(review.get("authority") or "customs").strip()
            if subject:
                queries.append(f'"{subject}" {authority} official court arrest seizure independent report {window_start} {window_end}')
    if china_count < max(1, len(items) // 2):
        queries.extend([
            f'customs seizure "from China" Chinese company shipment {window_start} {window_end}',
            f'border arrest "Chinese national" cargo customs {window_start} {window_end}',
            f'counterfeit drugs weapons shipment China-origin customs enforcement {window_start} {window_end}',
        ])
    undercovered = [name for name in ("United States", "Canada", "Australia", "Japan", "South Korea", "Singapore", "India", "Brazil", "Spain", "Germany") if not jurisdictions.get(name)]
    queries.extend(f'{country} customs seizure China shipment arrest {window_start} {window_end}' for country in undercovered[:8])
    return _unique(queries)[:32]


def _unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def _identity_tokens(item: CollectedItem) -> set[str]:
    entities = item.entities or {}
    values = []
    for key in ("container_numbers", "imo_numbers", "case_numbers", "bill_numbers", "companies", "people", "vessels"):
        values.extend(entities.get(key) or [])
    if not values:
        values.extend(re.findall(r"\b[A-Z]{4}\d{7}\b|\bIMO\s*\d{7}\b", " ".join((item.title or "", item.content or "")), flags=re.I))
    return {str(value).strip().casefold() for value in values if len(str(value).strip()) >= 5}


def _parse_json_object(text: str) -> dict:
    match = re.search(r"\{.*\}", str(text), flags=re.S)
    if not match:
        return {}
    try:
        value = json.loads(match.group(0))
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}
