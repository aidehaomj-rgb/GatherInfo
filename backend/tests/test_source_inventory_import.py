"""Tests for safe source-inventory parsing and deduplicated import."""
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import SourceConfig
from app.source_inventory_import import import_source_inventory, inventory_payload


def row(**overrides: str) -> dict[str, str]:
    values = {
        "id": "new-rss", "name": "New RSS", "channel": "rss",
        "collect_url": "https://example.com/feed/", "homepage_url": "https://example.com",
        "default_keywords": "trade、customs", "default_categories": "trade、policy",
        "languages": "en", "country_focus": "US、美国", "is_active": "是",
        "is_configured": "是", "allow_llm": "是", "health_status": "healthy",
        "description": "Example feed",
    }
    values.update(overrides)
    return values


def test_inventory_payload_parses_lists_status_and_group() -> None:
    payload = inventory_payload(row())
    assert payload["default_keywords"] == ["trade", "customs"]
    assert payload["country_focus"] == ["US", "美国"]
    assert payload["is_active"] is True
    assert payload["is_configured"] is True
    assert payload["source_group"] == "news_risk_media"


def test_inventory_payload_drops_country_placeholder() -> None:
    assert inventory_payload(row(country_focus="待核验"))["country_focus"] is None


def test_import_deduplicates_by_id_url_and_name_without_overwriting_state(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'sources.db'}")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    session.add_all([
        SourceConfig(
            id="same-id", name="Existing", channel="rss",
            base_url="https://existing.example/feed", is_active=False,
            is_configured=False, default_keywords=["old"], source_group="government_igo",
        ),
        SourceConfig(
            id="canonical-url", name="Canonical URL", channel="web_scrape",
            base_url="http://www.same.example/news/", is_active=False,
            is_configured=True, source_group="news_risk_media",
        ),
        SourceConfig(
            id="manual-source", name="Manual Source", channel="manual",
            is_active=False, is_configured=False, source_group="community_social",
        ),
        SourceConfig(
            id="ambiguous-a", name="Ambiguous A", channel="web_scrape",
            base_url="https://ambiguous.example/news", source_group="news_risk_media",
        ),
        SourceConfig(
            id="ambiguous-b", name="Ambiguous B", channel="rss",
            base_url="https://ambiguous.example/news/", source_group="news_risk_media",
        ),
    ])
    session.commit()

    rows = [
        row(id="same-id", name="Changed name", collect_url="https://changed.example",
            default_keywords="new", is_active="是", is_configured="是"),
        row(id="different-id", name="Duplicate URL", channel="web_scrape",
            collect_url="https://same.example/news"),
        row(id="another-duplicate", name="Same Duplicate URL", channel="web_scrape",
            collect_url="https://same.example/news/"),
        row(id="different-manual", name="Manual Source", channel="manual", collect_url=""),
        row(id="ambiguous-new", name="Ambiguous New", channel="web_scrape",
            collect_url="https://ambiguous.example/news"),
        row(id="shared-api-one", name="Shared API One", channel="json_api",
            collect_url="https://shared.example/api", default_keywords="one"),
        row(id="shared-api-two", name="Shared API Two", channel="json_api",
            collect_url="https://shared.example/api", default_keywords="two"),
        row(id="genuinely-new", name="Genuinely New", collect_url="https://new.example/feed"),
    ]
    result = import_source_inventory(session, rows)
    session.commit()

    assert result["inserted"] == 7
    assert result["skipped_exact_duplicates"] == 0
    assert result["conflicts"] == []
    assert session.query(SourceConfig).count() == 12
    existing = session.get(SourceConfig, "same-id")
    assert existing.name == "Existing"
    assert existing.base_url == "https://existing.example/feed"
    assert existing.is_active is False
    assert existing.is_configured is False
    assert existing.default_keywords == ["old", "new"]
    assert session.get(SourceConfig, "different-id") is not None
    assert session.get(SourceConfig, "another-duplicate") is not None
    assert session.get(SourceConfig, "different-manual") is not None
    assert session.get(SourceConfig, "ambiguous-new") is not None
    assert session.get(SourceConfig, "shared-api-one") is not None
    assert session.get(SourceConfig, "shared-api-two") is not None
    assert session.get(SourceConfig, "genuinely-new").source_group in {
        "news_risk_media", "government_igo", "community_social",
        "customs_enforcement", "regulation_trade_measures",
        "trade_commodity_data", "supply_chain_company",
        "search_aggregation", "procurement_opportunity",
    }
    session.close()
    engine.dispose()
