"""Pure collection-planning and batch-acceptance decisions.

The collection engine owns side effects.  This module deliberately accepts plain
objects and dictionaries so the decisions are deterministic and cheap to test.
"""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Mapping, Sequence
from urllib.parse import urlparse


SEMANTIC_CHANNELS = frozenset({"ai_research", "api_search"})
CORE_CHANNELS = frozenset({"official", "rss", "json_api"})
DEFAULT_CANDIDATE_BUDGET = 120
MAX_CANDIDATE_BUDGET = 300


@dataclass(frozen=True, slots=True)
class SourcePlan:
    """Immutable source portfolio for one collection round."""

    core: tuple[object, ...]
    discovery: tuple[object, ...]
    rotation: tuple[object, ...]

    @property
    def selected(self) -> tuple[object, ...]:
        return (*self.core, *self.discovery, *self.rotation)

    @property
    def selected_ids(self) -> tuple[str, ...]:
        return tuple(str(source.id) for source in self.selected)


def normalize_score(value: object) -> float:
    """Normalize historical 0..100 and current 0..1 scores to 0..1."""
    try:
        score = float(value or 0)
    except (TypeError, ValueError):
        return 0.0
    if score > 1:
        score /= 100
    return round(max(0.0, min(1.0, score)), 4)


def compute_dynamic_target(
    weekly_counts: Sequence[int],
    minimum: int,
    maximum: int,
) -> int:
    """Return P75 * 1.2 bounded by the topic policy."""
    floor = max(1, int(minimum))
    ceiling = max(floor, int(maximum))
    values = sorted(max(0, int(value)) for value in weekly_counts)
    if not values:
        return floor
    percentile_index = max(0, math.ceil(len(values) * 0.75) - 1)
    grown = math.ceil(values[percentile_index] * 1.2)
    return max(floor, min(ceiling, grown))


def candidate_budget(
    shortfall: int,
    floor: int = DEFAULT_CANDIDATE_BUDGET,
    ceiling: int = MAX_CANDIDATE_BUDGET,
) -> int:
    safe_floor = max(1, min(MAX_CANDIDATE_BUDGET, int(floor)))
    safe_ceiling = max(safe_floor, min(MAX_CANDIDATE_BUDGET, int(ceiling)))
    requested = max(safe_floor, max(0, int(shortfall)) * 6)
    return min(safe_ceiling, requested)


def build_source_plan(
    sources: Iterable[object],
    *,
    rotation_limit: int = 24,
    now: datetime | None = None,
) -> SourcePlan:
    """Select core, discovery and due long-tail sources without mutating config."""
    current = now or datetime.now(timezone.utc)
    available = tuple(source for source in sources if not _in_cooldown(source, current))
    core = tuple(source for source in available if _source_pool(source) == "core")
    discovery = tuple(
        source for source in available if _source_pool(source) == "discovery"
    )
    reserved_ids = {str(source.id) for source in (*core, *discovery)}
    rotating = [source for source in available if str(source.id) not in reserved_ids]
    rotating.sort(key=_rotation_priority)
    return SourcePlan(
        core=core,
        discovery=discovery,
        rotation=tuple(rotating[:max(0, int(rotation_limit))]),
    )


def evaluate_batch_metrics(
    items: Sequence[Mapping[str, object]],
    policy: Mapping[str, object],
) -> dict[str, object]:
    """Evaluate quantity, diversity and evidence coverage for one batch."""
    total = len(items)
    hosts = [str(item.get("source_host") or "").strip().casefold() for item in items]
    hosts = [host for host in hosts if host]
    regions = {
        str(item.get("jurisdiction") or "").strip().casefold()
        for item in items if str(item.get("jurisdiction") or "").strip()
    }
    high_grades = {
        str(value).strip().upper()
        for value in policy.get("high_evidence_grades", ["A", "B"])
    }
    high_evidence = sum(
        str(item.get("evidence_grade") or "").strip().upper() in high_grades
        for item in items
    )
    evidence_ratio = _ratio(high_evidence, total)
    required_fields = [
        str(field) for field in policy.get("required_structure_fields", []) if field
    ]
    structured = sum(
        all(
            any(item.get(option) not in (None, "", [], {}) for option in field.split("|"))
            for field in required_fields
        )
        for item in items
    ) if required_fields else total
    structure_ratio = _ratio(structured, total)
    date_complete = sum(bool(item.get("published_at")) for item in items)
    url_complete = sum(bool(item.get("url")) for item in items)
    host_counts = Counter(hosts)
    top_source_ratio = _ratio(max(host_counts.values(), default=0), total)
    metrics = {
        "items": total,
        "domains": len(host_counts),
        "regions": len(regions),
        "evidence_ratio": evidence_ratio,
        "structure_ratio": structure_ratio,
        "date_completeness": _ratio(date_complete, total),
        "url_completeness": _ratio(url_complete, total),
        "top_source_ratio": top_source_ratio,
    }
    checks = {
        "items": total >= int(policy.get("target_items", 0) or 0),
        "domains": len(host_counts) >= int(policy.get("min_domains", 0) or 0),
        "regions": len(regions) >= int(policy.get("min_regions", 0) or 0),
        "evidence_ratio": evidence_ratio >= float(
            policy.get("min_high_evidence_ratio", 0) or 0
        ),
        "source_concentration": top_source_ratio <= float(
            policy.get("max_top_source_ratio", 1) or 1
        ),
        "structure": structure_ratio >= float(policy.get("min_structure_ratio", 0) or 0),
        "formal_completeness": (
            _ratio(date_complete, total) == 1.0
            and _ratio(url_complete, total) == 1.0
        ) if total else False,
    }
    gaps = [name for name, passed in checks.items() if not passed]
    return {"passed": not gaps, "metrics": metrics, "checks": checks, "gaps": gaps}


def build_source_profile(source: object, context: object) -> dict[str, object]:
    """Infer a detached operational profile without overwriting attestations."""
    from app.collection_policy import evaluate_collection_policy

    previous = getattr(source, "collection_profile", None)
    profile = dict(previous) if isinstance(previous, Mapping) else {}
    channel = _source_channel(source)
    topic_id = str(getattr(context, "topic_id", "") or "")
    topics = [str(value) for value in profile.get("applicable_topics", []) if value]
    countries = getattr(source, "country_focus", None) or ()
    languages = getattr(source, "languages", None) or ()
    verdict = getattr(source, "last_verdict", None)
    verdict = verdict if isinstance(verdict, Mapping) else {}
    found = int(verdict.get("items_found", 0) or 0)
    new = int(verdict.get("items_new", 0) or 0)
    duplicates = int(verdict.get("duplicate_count", 0) or 0)
    source_grade = "A" if channel in {"official", "json_api"} else (
        "C" if channel in {"social", "deepweb"} else "B"
    )
    preferred_method = {
        "official": "official_api_rss_html",
        "json_api": "official_api_rss_html",
        "rss": "rss_sitemap_html",
        "web_scrape": "sitemap_html",
        "social": "manual_or_official_api",
        "deepweb": "manual_or_official_api",
    }.get(channel, "listing_html")
    decision = evaluate_collection_policy(source)
    seed_urls = [
        value for value in (
            getattr(source, "base_url", None),
            getattr(source, "homepage_url", None),
        ) if value
    ][:5]
    entrypoints = [*seed_urls, *list(getattr(source, "discovery_urls", None) or [])]
    automated = decision.automated_fetch_allowed and decision.content_depth == "full"
    return {
        **profile,
        "domain": _source_domain(source),
        "display_name": str(getattr(source, "name", "") or getattr(source, "id", "")),
        "source_type": _source_type(source),
        "applicable_topics": list(dict.fromkeys([*topics, topic_id])) if topic_id else topics,
        "countries": list(countries) if isinstance(countries, (list, tuple)) else [],
        "languages": list(languages) if isinstance(languages, (list, tuple)) else [],
        "document_types": list(getattr(context, "document_types", ()) or ()),
        "collection_method": channel,
        "preferred_method": preferred_method,
        "schedule": "daily" if channel in {"rss", "api_search", "ai_research"} else "weekly",
        "seed_urls": seed_urls,
        "discovery_urls": list(getattr(source, "discovery_urls", None) or []),
        "entrypoints": list(dict.fromkeys(entrypoints))[:8],
        "pagination_capable": channel in {"official", "json_api", "web_scrape", "deepweb"},
        "publication_date_method": "api_or_feed" if channel in {"official", "rss", "json_api"} else "page_metadata",
        "content_method": "detail_page" if channel in {"rss", "web_scrape", "api_search", "ai_research"} else "api_payload",
        "source_grade": source_grade,
        "verification_status": str(getattr(source, "verification_status", "unverified") or "unverified"),
        "robots_status": str(getattr(source, "robots_status", "unverified") or "unverified"),
        "terms_status": str(getattr(source, "terms_status", "unverified") or "unverified"),
        "llm_ingest_allowed": bool(getattr(source, "llm_ingest_allowed", False)),
        "origin_resolution_required": bool(getattr(source, "origin_resolution_required", True)),
        "crawl_delay_seconds": max(5, int(getattr(source, "crawl_delay_seconds", 5) or 5)),
        "automated_fetch_allowed": automated,
        "block_reason": None if automated else decision.reason,
        "health_status": str(getattr(source, "health_status", "unknown") or "unknown"),
        "topic_yield_rate": round(new / found, 4) if found else 0.0,
        "duplicate_rate": round(duplicates / found, 4) if found else 0.0,
    }


def _ratio(value: int, total: int) -> float:
    return round(value / total, 4) if total else 0.0


def _source_channel(source: object) -> str:
    raw = getattr(source, "channel", "")
    return str(getattr(raw, "value", raw)).strip().casefold()


def _source_domain(source: object) -> str:
    for attr in ("base_url", "homepage_url", "api_endpoint"):
        value = str(getattr(source, attr, "") or "").strip()
        if value:
            host = urlparse(value).netloc.casefold()
            if host.startswith("www."):
                host = host[4:]
            return host.split(":", 1)[0]
    return ""


def _source_type(source: object) -> str:
    channel = _source_channel(source)
    group = str(getattr(source, "source_group", "") or "").casefold()
    if channel in {"official", "json_api"} or "official" in group:
        return "official_government"
    if channel in {"social", "deepweb"}:
        return "social_platform"
    if channel in {"rss", "api_search", "ai_research"}:
        return "news_media"
    return "specialist_or_media"


def _source_pool(source: object) -> str:
    profile = getattr(source, "collection_profile", None)
    configured = str((profile or {}).get("pool") or "").strip().casefold() \
        if isinstance(profile, Mapping) else ""
    if configured in {"core", "discovery", "rotation", "supplement"}:
        return configured
    channel = _source_channel(source)
    if channel in SEMANTIC_CHANNELS:
        return "discovery"
    if channel in CORE_CHANNELS:
        return "core"
    return "rotation"


def _in_cooldown(source: object, now: datetime) -> bool:
    value = getattr(source, "cooldown_until", None)
    if value is None:
        return False
    aware = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return aware > now


def _rotation_priority(source: object) -> tuple[float, float, str]:
    last_collected = getattr(source, "last_collected_at", None)
    if last_collected is None:
        collected_timestamp = float("-inf")
    else:
        aware = (
            last_collected.replace(tzinfo=timezone.utc)
            if last_collected.tzinfo is None else last_collected
        )
        collected_timestamp = aware.timestamp()
    verdict = getattr(source, "last_verdict", None)
    yield_value = float((verdict or {}).get("items_new", 0) or 0) if isinstance(verdict, dict) else 0
    return collected_timestamp, -yield_value, str(getattr(source, "id", ""))


__all__ = [
    "SourcePlan",
    "build_source_plan",
    "candidate_budget",
    "build_source_profile",
    "compute_dynamic_target",
    "evaluate_batch_metrics",
    "normalize_score",
]
