"""Immutable topic intent shared by collection planning and quality review."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, timedelta
from typing import Any, Mapping


RELEVANCE_TIERS = ("china_direct", "china_transmission", "global_reference")
EVIDENCE_GRADES = ("A", "B", "C")
SIX_OPTIMIZED_TOPIC_IDS = frozenset({
    "item-56adc0",
    "global-trade",
    "foreign-trade-forum-risk-monitoring",
    "weekly-enforcement-intelligence",
    "tech-regulations",
    "weekly-trade-current-affairs",
})


@dataclass(frozen=True)
class ResearchWindow:
    start: date
    end: date


@dataclass(frozen=True)
class TopicCollectionPolicy:
    weekly_target: tuple[int, int]
    minimum_domains: int
    minimum_regions: int
    preferred_evidence_grades: tuple[str, ...]
    minimum_preferred_evidence_ratio: float
    minimum_quality: float = 0.70
    minimum_relevance: float = 0.70
    max_rounds: int = 2
    candidate_floor: int = 120
    candidate_ceiling: int = 300
    per_source_review_limit: int = 160
    max_top_source_ratio: float | None = None


@dataclass(frozen=True)
class TopicResearchContext:
    topic_id: str
    name: str
    description: str
    keywords: tuple[str, ...]
    synonyms: tuple[str, ...]
    exclude_keywords: tuple[str, ...]
    categories: tuple[str, ...]
    focus_countries: tuple[str, ...]
    focus_languages: tuple[str, ...]
    target_urls: tuple[str, ...]
    target_urls_mode: str
    prompt: str
    window: ResearchWindow
    search_dimensions: tuple[str, ...]
    policy_instruments: tuple[str, ...]
    products: tuple[str, ...]
    actors: tuple[str, ...]
    routes: tuple[str, ...]
    document_types: tuple[str, ...]
    source_grades: tuple[str, ...]
    allowed_collection_methods: tuple[str, ...]
    relevance_tiers: tuple[str, ...]
    evidence_grades: tuple[str, ...]
    policy: TopicCollectionPolicy
    literal_keyword_bypass_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Return a detached JSON-safe value for prompts and run diagnostics."""
        return {
            "topic_id": self.topic_id,
            "name": self.name,
            "description": self.description,
            "keywords": list(self.keywords),
            "synonyms": list(self.synonyms),
            "exclude_keywords": list(self.exclude_keywords),
            "categories": list(self.categories),
            "focus_countries": list(self.focus_countries),
            "focus_languages": list(self.focus_languages),
            "target_urls": list(self.target_urls),
            "target_urls_mode": self.target_urls_mode,
            "prompt": self.prompt,
            "collection_window_start": self.window.start.isoformat(),
            "collection_window_end": self.window.end.isoformat(),
            "search_dimensions": list(self.search_dimensions),
            "policy_instruments": list(self.policy_instruments),
            "products": list(self.products),
            "actors": list(self.actors),
            "routes": list(self.routes),
            "document_types": list(self.document_types),
            "source_grades": list(self.source_grades),
            "allowed_collection_methods": list(self.allowed_collection_methods),
            "relevance_tiers": list(self.relevance_tiers),
            "evidence_grades": list(self.evidence_grades),
            "policy": {**asdict(self.policy), "weekly_target": list(self.policy.weekly_target)},
            "literal_keyword_bypass_allowed": self.literal_keyword_bypass_allowed,
        }


_COMMON_METHODS = ("rss", "official_api", "json_api", "web", "search", "pdf")
_COMMON_DOCS = ("official_notice", "regulation", "enforcement_case", "news", "pdf")


def _policy(target: tuple[int, int], domains: int, regions: int, grades: tuple[str, ...], ratio: float) -> TopicCollectionPolicy:
    return TopicCollectionPolicy(target, domains, regions, grades, ratio)


TOPIC_DEFAULTS: Mapping[str, Mapping[str, Any]] = {
    "item-56adc0": {
        "dimensions": ("jurisdiction", "control_list", "licence", "end_user", "evasion", "controlled_product"),
        "instruments": ("export_control", "entity_list", "licensing", "extraterritoriality", "enforcement"),
        "documents": _COMMON_DOCS,
        "policy": _policy((10, 20), 8, 4, ("A",), 0.60),
    },
    "global-trade": {
        "dimensions": ("jurisdiction", "policy_stage", "product", "origin", "trade_agreement", "customs_procedure"),
        "instruments": ("tariff", "anti_dumping", "countervailing", "safeguard", "rules_of_origin", "fta", "de_minimis"),
        "documents": _COMMON_DOCS,
        "policy": _policy((15, 30), 12, 5, ("A",), 0.50),
    },
    "foreign-trade-forum-risk-monitoring": {
        "dimensions": ("conduct", "goods", "route", "actor", "clearance_stage", "corroboration"),
        "instruments": ("double_clearance", "undervaluation", "false_export", "origin_evasion", "licence_evasion"),
        "documents": ("forum_post", "community_thread", "professional_analysis", "official_case"),
        "methods": (*_COMMON_METHODS, "forum"),
        "policy": _policy((10, 20), 6, 1, ("B", "C"), 0.60),
    },
    "weekly-enforcement-intelligence": {
        "dimensions": ("jurisdiction", "authority", "case_number", "actor", "goods", "quantity", "route", "conduct"),
        "instruments": ("seizure", "detention", "penalty", "prosecution", "forfeiture", "export_control_enforcement"),
        "documents": ("official_release", "court_document", "case_notice", "news", "pdf"),
        "policy": _policy((40, 60), 12, 8, ("A",), 0.70),
    },
    "tech-regulations": {
        "dimensions": ("market", "product", "measure_stage", "effective_date", "conformity_assessment", "transition_period"),
        "instruments": ("tbt", "sps", "standard", "inspection", "quarantine", "recall", "carbon_footprint", "digital_product_passport"),
        "documents": ("wto_notification", "regulation", "consultation", "standard", "recall", "pdf"),
        "policy": _policy((20, 30), 10, 6, ("A",), 0.70),
    },
    "weekly-trade-current-affairs": {
        "dimensions": ("event_change", "supply_demand", "price", "logistics", "trade_impact", "customs_control"),
        "instruments": ("policy_change", "market_disruption", "supply_chain_risk", "enforcement", "route_change"),
        "documents": _COMMON_DOCS,
        "policy": _policy((15, 30), 10, 5, ("A", "B"), 0.50),
    },
}


_GENERIC_DEFAULT = {
    "dimensions": ("topic", "jurisdiction", "product", "actor", "route"),
    "instruments": (),
    "documents": _COMMON_DOCS,
    "policy": TopicCollectionPolicy((10, 20), 5, 2, ("A", "B"), 0.50),
}


def build_topic_research_context(
    topic: Any,
    *,
    prompt: str | None = None,
    window_start: date | None = None,
    window_end: date | None = None,
    policy_override: Mapping[str, Any] | None = None,
) -> TopicResearchContext:
    """Build one immutable interpretation of a topic for the entire run."""
    topic_id = str(getattr(topic, "id", "") or "")
    defaults = TOPIC_DEFAULTS.get(topic_id, _GENERIC_DEFAULT)
    end = window_end or date.today()
    days = max(1, int(getattr(topic, "collect_window_days", 7) or 7))
    start = window_start or (end - timedelta(days=days))
    combined_prompt = _merge_text(getattr(topic, "description_prompt", None), prompt)
    base_policy = defaults["policy"]
    topic_override = getattr(topic, "collection_policy", None)
    override = policy_override or _policy_mapping(topic_override)
    policy = _merge_policy(base_policy, override)
    return TopicResearchContext(
        topic_id=topic_id,
        name=str(getattr(topic, "name", "") or ""),
        description=str(getattr(topic, "description", "") or ""),
        keywords=_text_tuple(getattr(topic, "keywords", None)),
        synonyms=_text_tuple(getattr(topic, "synonyms", None)),
        exclude_keywords=_text_tuple(getattr(topic, "exclude_keywords", None)),
        categories=_text_tuple(getattr(topic, "categories", None)),
        focus_countries=_text_tuple(getattr(topic, "focus_countries", None)),
        focus_languages=_text_tuple(getattr(topic, "focus_languages", None)),
        target_urls=_text_tuple(getattr(topic, "target_urls", None)),
        target_urls_mode=_target_urls_mode(getattr(topic, "target_urls_mode", None)),
        prompt=combined_prompt,
        window=ResearchWindow(start=start, end=end),
        search_dimensions=tuple(defaults["dimensions"]),
        policy_instruments=tuple(defaults["instruments"]),
        products=_text_tuple(getattr(topic, "products", None)),
        actors=_text_tuple(getattr(topic, "actors", None)),
        routes=_text_tuple(getattr(topic, "routes", None)),
        document_types=tuple(defaults["documents"]),
        source_grades=("A", "B", "C"),
        allowed_collection_methods=tuple(defaults.get("methods", _COMMON_METHODS)),
        relevance_tiers=RELEVANCE_TIERS,
        evidence_grades=EVIDENCE_GRADES,
        policy=policy,
    )


def ensure_topic_research_context(value: Any, **kwargs: Any) -> TopicResearchContext:
    if isinstance(value, TopicResearchContext):
        return value
    return build_topic_research_context(value, **kwargs)


def _text_tuple(value: Any) -> tuple[str, ...]:
    values = value if isinstance(value, (list, tuple, set, frozenset)) else ()
    cleaned = (str(entry).strip() for entry in values)
    return tuple(dict.fromkeys(entry for entry in cleaned if entry))


def _target_urls_mode(value: Any) -> str:
    return "explicit" if str(value or "").casefold() == "explicit" else "discovery"


def _merge_text(*values: Any) -> str:
    cleaned = (str(value).strip() for value in values if value)
    return "\n\n".join(dict.fromkeys(value for value in cleaned if value))


def _merge_policy(base: TopicCollectionPolicy, override: Mapping[str, Any]) -> TopicCollectionPolicy:
    aliases = {
        "weekly_target_min": "_weekly_target_min",
        "weekly_target_max": "_weekly_target_max",
        "min_independent_domains": "minimum_domains",
        "min_regions": "minimum_regions",
        "min_primary_source_ratio": "minimum_preferred_evidence_ratio",
        "quality_threshold": "minimum_quality",
        "relevance_threshold": "minimum_relevance",
    }
    translated = {aliases.get(key, key): value for key, value in override.items()}
    weekly_target = (
        int(translated.pop("_weekly_target_min", base.weekly_target[0]) or base.weekly_target[0]),
        int(translated.pop("_weekly_target_max", base.weekly_target[1]) or base.weekly_target[1]),
    )
    allowed = set(asdict(base))
    values = {key: value for key, value in translated.items() if key in allowed}
    values = {**values, "weekly_target": weekly_target}
    if "weekly_target" in values:
        values = {**values, "weekly_target": tuple(values["weekly_target"])}
    if "preferred_evidence_grades" in values:
        values = {**values, "preferred_evidence_grades": tuple(values["preferred_evidence_grades"])}
    return TopicCollectionPolicy(**{**asdict(base), **values})


def _policy_mapping(value: Any) -> Mapping[str, Any]:
    if isinstance(value, Mapping):
        return value
    dump = getattr(value, "model_dump", None)
    return dump(exclude_none=True) if callable(dump) else {}
