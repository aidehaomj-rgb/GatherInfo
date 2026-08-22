from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.collection_strategy import (
    build_source_plan, build_source_profile,
    candidate_budget,
    compute_dynamic_target,
    evaluate_batch_metrics,
    normalize_score,
)


def _source(source_id: str, channel: str, *, days_ago: int = 0, failures: int = 0):
    return SimpleNamespace(
        id=source_id,
        channel=channel,
        source_group="official" if channel == "official" else "other",
        country_focus=["US"] if source_id.endswith("us") else [],
        languages=["en"],
        default_categories=[],
        last_collected_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
        cooldown_until=None,
        consecutive_failures=failures,
        last_verdict={"items_new": 2 if source_id.startswith("yield") else 0},
        collection_profile=None,
    )


def test_dynamic_target_uses_p75_growth_and_policy_bounds():
    assert compute_dynamic_target([5, 8, 10, 12, 15, 18, 20, 30], 10, 20) == 20
    assert compute_dynamic_target([], 15, 30) == 15
    assert compute_dynamic_target([1, 1, 2], 10, 20) == 10


def test_candidate_budget_scales_with_shortfall_and_is_bounded():
    assert candidate_budget(0) == 120
    assert candidate_budget(30) == 180
    assert candidate_budget(100) == 300


def test_source_plan_keeps_core_and_discovery_then_rotates_oldest_sources():
    sources = [
        _source("official-us", "official", days_ago=1),
        _source("research", "ai_research", days_ago=1),
        _source("recent", "web_scrape", days_ago=1),
        _source("oldest", "web_scrape", days_ago=40),
        _source("yield-source", "web_scrape", days_ago=20),
    ]

    plan = build_source_plan(sources, rotation_limit=2)

    assert [source.id for source in plan.core] == ["official-us"]
    assert [source.id for source in plan.discovery] == ["research"]
    assert [source.id for source in plan.rotation] == ["oldest", "yield-source"]
    assert plan.selected_ids == ("official-us", "research", "oldest", "yield-source")


def test_source_plan_excludes_sources_in_runtime_cooldown():
    cooling = _source("cooling", "web_scrape", failures=3)
    cooling.cooldown_until = datetime.now(timezone.utc) + timedelta(hours=1)

    assert build_source_plan([cooling], rotation_limit=10).selected_ids == ()


def test_source_profile_is_detached_and_carries_operational_dimensions():
    source = _source("official-us", "official")
    source.collection_profile = {"pool": "core", "operator_note": "keep"}
    source.verification_status = "verified"
    source.health_status = "healthy"
    context = SimpleNamespace(
        topic_id="global-trade",
        document_types=("official_notice", "regulation"),
    )

    profile = build_source_profile(source, context)

    assert profile is not source.collection_profile
    assert profile["pool"] == "core"
    assert profile["operator_note"] == "keep"
    assert profile["applicable_topics"] == ["global-trade"]
    assert profile["source_grade"] == "A"
    assert profile["publication_date_method"] == "api_or_feed"


def test_batch_acceptance_reports_quantity_source_and_evidence_gaps():
    metrics = evaluate_batch_metrics(
        [
            {"source_host": "a.gov", "jurisdiction": "US", "evidence_grade": "A", "url": "https://a.gov/1", "published_at": "2026-08-17"},
            {"source_host": "b.example", "jurisdiction": "EU", "evidence_grade": "B", "url": "https://b.example/2", "published_at": "2026-08-17"},
        ],
        {
            "target_items": 3,
            "min_domains": 3,
            "min_regions": 2,
            "min_high_evidence_ratio": 0.6,
            "high_evidence_grades": ["A"],
            "max_top_source_ratio": 0.6,
        },
    )

    assert metrics["passed"] is False
    assert set(metrics["gaps"]) == {"items", "domains", "evidence_ratio"}
    assert metrics["metrics"]["regions"] == 2


def test_scores_are_normalized_to_zero_one():
    assert normalize_score(85) == 0.85
    assert normalize_score(0.72) == 0.72
    assert normalize_score(-4) == 0.0
    assert normalize_score(999) == 1.0
