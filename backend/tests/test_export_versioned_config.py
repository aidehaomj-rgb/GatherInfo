from backend.scripts.export_versioned_config import CONTENT_TABLES, SUPPLY_CHAIN_MODELS, sanitize


def test_sanitize_redacts_credentials_without_redacting_keyword_settings() -> None:
    value = {
        "api_key": "secret-value",
        "nested": {"access_token": "token-value", "keyword_param": "query"},
        "prefer_default_keywords": True,
    }

    assert sanitize(value) == {
        "api_key": "${REDACTED}",
        "nested": {"access_token": "${REDACTED}", "keyword_param": "query"},
        "prefer_default_keywords": True,
    }


def test_supply_chain_snapshot_covers_every_page_dataset() -> None:
    assert set(SUPPLY_CHAIN_MODELS) == {
        "investigations",
        "entities",
        "cases",
        "shipments",
        "evidence",
        "open_source_evidence",
        "reports",
    }


def test_content_archive_covers_collected_items_reports_and_research() -> None:
    assert {"collected_items", "reports", "tags", "item_tags"}.issubset(CONTENT_TABLES)
    assert {"research_jobs", "research_cases", "research_entities", "research_evidence"}.issubset(CONTENT_TABLES)
