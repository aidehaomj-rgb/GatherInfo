"""Idempotent installation of evidence-reviewed global official sources."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.collection_policy import evaluate_collection_policy
from app.database import Base
from app.models import SourceConfig, Topic
from app.verified_source_catalog import install_verified_global_sources


def test_catalog_installs_verified_sources_and_binds_weekly_topic_idempotently() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add_all([
            Topic(
                id="global-trade", name="全球贸易",
                source_ids=["existing-source"], weekly_digest_enabled=True,
            ),
            SourceConfig(
                id="cbp-newsroom", name="Legacy CBP scraper",
                channel="web_scrape", base_url="https://www.cbp.gov/newsroom/national-media-release",
                is_active=True, is_configured=True,
            ),
            SourceConfig(
                id="ext-src-060", name="Legacy ABF scraper",
                channel="web_scrape", base_url="https://www.abf.gov.au/sitenewsroom",
                is_active=True, is_configured=True,
            ),
            SourceConfig(
                id="brazil-mdic-rss", name="Broken MDIC feed",
                channel="rss", base_url="https://www.gov.br/mdic/rss.xml",
                is_active=True, is_configured=True,
            ),
        ])
        db.commit()

        first = install_verified_global_sources(db)
        second = install_verified_global_sources(db)

        assert first["created"] == [
            "federal-register-trade", "federal-register-ita",
            "federal-register-usitc", "federal-register-ustr",
            "federal-register-cbp", "brazil-receita-rss", "abf-newsroom-rss",
            "eu-daily-news-rss", "uk-dbt-rss", "cbp-rss",
        ]
        assert first["bound"] == first["created"]
        assert second == {
            "created": [], "refreshed": [], "verified": [], "bound": [],
            "deactivated": [],
        }
        assert first["deactivated"] == [
            "brazil-mdic-rss", "cbp-newsroom", "ext-src-060",
        ]
        for source_id in first["deactivated"]:
            source = db.get(SourceConfig, source_id)
            assert source.is_active is False
            assert "受管官方源" in source.compliance_note
        topic = db.get(Topic, "global-trade")
        assert topic.source_ids == [
            "existing-source", "federal-register-trade",
            "federal-register-ita", "federal-register-usitc",
            "federal-register-ustr", "federal-register-cbp",
            "brazil-receita-rss", "abf-newsroom-rss",
            "eu-daily-news-rss", "uk-dbt-rss", "cbp-rss",
        ]
        sources = {
            source.id: source for source in db.query(SourceConfig).filter(
                SourceConfig.id.in_(first["created"]),
            ).all()
        }
        assert all(
            evaluate_collection_policy(source).content_depth == "full"
            for source in sources.values()
        )
        federal = sources["federal-register-trade"]
        assert federal.auth_config["items_path"] == "results"
        assert federal.auth_config["fields"]["content"] == "abstract"
        assert federal.auth_config["window_start_param"] == (
            "conditions[publication_date][gte]"
        )
        assert federal.auth_config["prefer_default_keywords"] is True
        assert sources["brazil-receita-rss"].auth_config[
            "defer_keyword_filter_to_llm"
        ] is True
        assert sources["eu-daily-news-rss"].base_url.endswith("?language=en")
        assert sources["eu-daily-news-rss"].auth_config[
            "defer_keyword_filter_to_llm"
        ] is True
        assert sources["uk-dbt-rss"].auth_config[
            "defer_keyword_filter_to_llm"
        ] is True
        assert sources["cbp-rss"].auth_config[
            "defer_keyword_filter_to_llm"
        ] is True
        assert sources["federal-register-ita"].auth_config["query"][
            "conditions[agencies][]"
        ] == "international-trade-administration"
        assert "keyword_param" not in sources["federal-register-ita"].auth_config

        federal.auth_config = {"stale": True}
        db.commit()
        refreshed = install_verified_global_sources(db, refresh_managed=True)
        db.refresh(federal)

        assert refreshed["refreshed"] == [
            "federal-register-trade", "federal-register-ita",
            "federal-register-usitc", "federal-register-ustr",
            "federal-register-cbp", "brazil-receita-rss", "abf-newsroom-rss",
            "eu-daily-news-rss", "uk-dbt-rss", "cbp-rss",
        ]
        assert federal.auth_config["window_end_param"] == (
            "conditions[publication_date][lte]"
        )
    finally:
        db.close()
        engine.dispose()
