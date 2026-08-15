"""Measurable acceptance criteria for research collections."""
from __future__ import annotations

from urllib.parse import urlparse

from app.models import CollectedItem
from app.translation_service import needs_translation, translation_payload

DEFAULT_POLICY = {
    "min_items": 10,
    "min_strong_china_ratio": 0.5,
    "min_china_ratio": 0.6,
    "min_non_hk_jurisdictions": 5,
    "min_entity_rate": 0.7,
    "min_verified_rate": 0.5,
    "min_official_rate": 0.4,
    "min_translation_rate": 1.0,
}


def evaluate_acceptance(items: list[CollectedItem], policy: dict | None = None) -> dict:
    rules = {**DEFAULT_POLICY, **(policy or {})}
    total = len(items)
    strong_china = china = verified = entity_complete = official = translation_required = translated = 0
    jurisdictions = set()
    for item in items:
        metadata = item.raw_metadata or {}
        review = metadata.get("enforcement_review") or {}
        research = metadata.get("entity_research") or {}
        relevance = review.get("china_relevance_level")
        strong_china += relevance == "strong"
        china += relevance in {"strong", "weak"}
        jurisdiction = str(review.get("jurisdiction") or "").strip()
        if jurisdiction and jurisdiction.casefold() not in {"hong kong", "香港"}:
            jurisdictions.add(jurisdiction)
        verified += research.get("cross_source_status") == "verified"
        values = [value for key, value in (item.entities or {}).items() if isinstance(value, list) and value]
        entity_complete += bool(values) or bool((item.entities or {}).get("subject"))
        host = urlparse(item.url or "").netloc.casefold()
        official += any(marker in host for marker in (".gov", ".gc.ca", ".gov.au", ".gov.uk", ".europa.eu", "police", "customs"))
        if needs_translation(item.language, f"{item.title} {item.summary or ''}"):
            translation_required += 1
            translated += bool(translation_payload(metadata))
    ratio = lambda value, denominator=total: round(value / denominator, 3) if denominator else 0.0
    metrics = {
        "items": total, "strong_china_ratio": ratio(strong_china), "china_ratio": ratio(china), "non_hk_jurisdictions": len(jurisdictions),
        "entity_rate": ratio(entity_complete), "verified_rate": ratio(verified),
        "official_rate": ratio(official),
        "translation_rate": ratio(translated, translation_required) if translation_required else 1.0,
    }
    checks = {
        "items": total >= int(rules["min_items"]),
        "strong_china_ratio": metrics["strong_china_ratio"] >= float(rules["min_strong_china_ratio"]),
        "china_ratio": metrics["china_ratio"] >= float(rules["min_china_ratio"]),
        "non_hk_jurisdictions": metrics["non_hk_jurisdictions"] >= int(rules["min_non_hk_jurisdictions"]),
        "entity_rate": metrics["entity_rate"] >= float(rules["min_entity_rate"]),
        "verified_rate": metrics["verified_rate"] >= float(rules["min_verified_rate"]),
        "official_rate": metrics["official_rate"] >= float(rules["min_official_rate"]),
        "translation_rate": metrics["translation_rate"] >= float(rules["min_translation_rate"]),
    }
    gaps = [name for name, passed in checks.items() if not passed]
    return {"passed": not gaps, "policy": rules, "metrics": metrics, "checks": checks, "gaps": gaps}


def acceptance_followups(result: dict, start: str, end: str) -> list[str]:
    gaps = set(result.get("gaps") or [])
    queries = []
    if "strong_china_ratio" in gaps or "china_ratio" in gaps:
        queries += [f'customs seizure "from China" company shipment {start} {end}', f'border arrest "Chinese national" cargo {start} {end}']
    if "non_hk_jurisdictions" in gaps:
        queries += [f'{country} customs seizure China official {start} {end}' for country in ("US", "Canada", "Australia", "Japan", "Korea", "India", "Brazil")]
    if "verified_rate" in gaps:
        queries.append(f'court indictment customs seizure company vessel case number {start} {end}')
    if "official_rate" in gaps:
        queries.append(f'site:gov customs border seizure arrest official {start} {end}')
    if "entity_rate" in gaps:
        queries.append(f'customs seizure company name container vessel flight case number {start} {end}')
    return queries[:16]
