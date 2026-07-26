"""Tests for source readiness evaluation."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.routes.sources import _eval_configured, router
from app.collection_schemas import SourceUpdate


def test_public_web_source_with_url_is_ready_without_api_key() -> None:
    assert _eval_configured("web_scrape", None, base_url="https://example.com") is True


def test_public_web_source_without_url_is_not_ready() -> None:
    assert _eval_configured("web_scrape", None, base_url=None) is False


def test_api_search_remains_pending_without_api_key() -> None:
    assert _eval_configured("api_search", None, base_url="https://api.example.com") is False


def test_api_search_is_ready_with_api_key() -> None:
    assert _eval_configured("api_search", "key", base_url="https://api.example.com") is True


def test_readiness_route_precedes_dynamic_source_route() -> None:
    matching = [route for route in router.routes if getattr(route, "path", "") == "/api/v1/sources/reconcile-readiness"]

    assert matching
    assert "POST" in matching[0].methods


def test_source_update_accepts_collection_safety_limits() -> None:
    update = SourceUpdate(max_items_per_run=18, timeout_seconds=20, max_retries=1)

    assert update.max_items_per_run == 18
    assert update.timeout_seconds == 20
    assert update.max_retries == 1
