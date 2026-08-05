"""Decision-matrix tests for collection compliance policy."""
from pathlib import Path
from types import SimpleNamespace
import sys

import pytest
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.collection_policy import evaluate_collection_policy
from app.routes.sources import collection_readiness


def source(**overrides: object) -> SimpleNamespace:
    defaults = {
        "id": "source-test",
        "name": "Source test",
        "is_active": True,
        "is_configured": True,
        "verification_status": "verified",
        "robots_status": "allowed",
        "terms_status": "public_domain_with_exceptions",
        "llm_ingest_allowed": True,
    }
    return SimpleNamespace(**{**defaults, **overrides})


@pytest.mark.parametrize(
    ("overrides", "reason_fragment"),
    (
        ({"is_active": False}, "未启用"),
        ({"is_configured": False}, "未完成配置"),
        ({"verification_status": "blocked"}, "核验状态"),
        ({"verification_status": "denied_by_owner"}, "核验状态"),
        ({"robots_status": "blocked_cloudflare"}, "robots"),
        ({"robots_status": "denied_all"}, "robots"),
        ({"robots_status": "allowed_but_denied"}, "robots"),
        ({"terms_status": "blocked"}, "条款"),
        ({"terms_status": "denied_for_automation"}, "条款"),
    ),
)
def test_inactive_unconfigured_or_denied_sources_are_rejected(
    overrides: dict[str, object],
    reason_fragment: str,
) -> None:
    decision = evaluate_collection_policy(source(**overrides))

    assert decision.automated_fetch_allowed is False
    assert decision.llm_ingest_allowed is False
    assert decision.content_depth == "metadata"
    assert reason_fragment in decision.reason


@pytest.mark.parametrize(
    ("verification_status", "robots_status", "terms_status"),
    (
        ("verified", "allowed", "allowed"),
        (
            "verified_2026-07-31",
            "allowed_with_disallows",
            "public_domain_with_exceptions",
        ),
        (
            "verified_2026-08-04",
            "allowed_disallow_search",
            "government_conditions_apply",
        ),
        (
            "verified_2026-08-04",
            "allowed_crawl_delay_40",
            "linking_allowed_logo_restricted",
        ),
        (
            "verified_2026-08-04",
            "allowed_with_disallows",
            "cc_by_4_0_with_exceptions",
        ),
    ),
)
def test_verified_permitted_source_allows_full_llm_processing(
    verification_status: str,
    robots_status: str,
    terms_status: str,
) -> None:
    decision = evaluate_collection_policy(source(
        verification_status=verification_status,
        robots_status=robots_status,
        terms_status=terms_status,
    ))

    assert decision.automated_fetch_allowed is True
    assert decision.llm_ingest_allowed is True
    assert decision.content_depth == "full"


def test_llm_opt_out_never_allows_full_content_ingestion() -> None:
    decision = evaluate_collection_policy(source(llm_ingest_allowed=False))

    assert decision.automated_fetch_allowed is True
    assert decision.llm_ingest_allowed is False
    assert decision.content_depth == "excerpt"
    assert "LLM" in decision.reason


def test_legacy_unverified_source_is_limited_to_existing_connector_excerpt() -> None:
    decision = evaluate_collection_policy(source(
        verification_status="legacy_unverified",
        robots_status="unverified",
        terms_status="unverified",
        llm_ingest_allowed=True,
    ))

    assert decision.automated_fetch_allowed is True
    assert decision.llm_ingest_allowed is False
    assert decision.content_depth == "excerpt"
    assert "现有连接器" in decision.reason


def test_new_unverified_source_fails_closed_before_network_access() -> None:
    decision = evaluate_collection_policy(source(
        verification_status="unverified",
        robots_status="unverified",
        terms_status="unverified",
    ))

    assert decision.automated_fetch_allowed is False
    assert decision.llm_ingest_allowed is False
    assert decision.content_depth == "metadata"
    assert "尚未核验" in decision.reason


@pytest.mark.parametrize(
    ("field", "status", "reason_fragment"),
    (
        ("robots_status", "denied_all", "robots"),
        ("terms_status", "blocked", "条款"),
    ),
)
def test_explicit_denial_overrides_legacy_compatibility(
    field: str,
    status: str,
    reason_fragment: str,
) -> None:
    decision = evaluate_collection_policy(source(**{
        "verification_status": "legacy_unverified",
        field: status,
    }))

    assert decision.automated_fetch_allowed is False
    assert decision.llm_ingest_allowed is False
    assert decision.content_depth == "metadata"
    assert reason_fragment in decision.reason


@pytest.mark.parametrize(
    ("overrides", "reason_fragment"),
    (
        ({"verification_status": "partial"}, "尚未核验"),
        ({"robots_status": "unverified"}, "robots"),
        ({"terms_status": "license_required_for_ai"}, "条款"),
    ),
)
def test_unknown_or_unapproved_statuses_fail_closed(
    overrides: dict[str, object],
    reason_fragment: str,
) -> None:
    decision = evaluate_collection_policy(source(**overrides))

    assert decision.automated_fetch_allowed is False
    assert decision.llm_ingest_allowed is False
    assert decision.content_depth == "metadata"
    assert reason_fragment in decision.reason


def test_policy_decision_is_immutable() -> None:
    decision = evaluate_collection_policy(source())

    with pytest.raises((AttributeError, TypeError)):
        setattr(decision, "content_depth", "metadata")


def test_collection_readiness_reports_full_excerpt_and_blocked_counts() -> None:
    db = MagicMock()
    db.query.return_value.filter.return_value.all.return_value = [
        source(),
        source(
            verification_status="legacy_unverified",
            robots_status="unverified",
            terms_status="unverified",
        ),
        source(robots_status="denied_all"),
    ]

    result = collection_readiness(db)

    assert result["total_active"] == 3
    assert result["ready_full"] == 1
    assert result["excerpt_only"] == 1
    assert result["blocked"] == 1
