"""Known verified-source profile reconciliation tests."""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.collection_policy import evaluate_collection_policy
from app.database import Base
from app.models import SourceChannel, SourceConfig
from app.source_profile_registry import reconcile_verified_source_profiles


def test_reconciliation_promotes_known_legacy_source_and_preserves_user_profile():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        SourceConfig(
            id="cbp", name="CBP", channel=SourceChannel.WEB_SCRAPE,
            base_url="https://www.cbp.gov/newsroom/media-releases/all",
            is_active=True, is_configured=True,
            verification_status="legacy_unverified",
        ),
        SourceConfig(
            id="custom", name="Custom", channel=SourceChannel.WEB_SCRAPE,
            base_url="https://www.gov.uk/news",
            is_active=True, is_configured=True,
            verification_status="verified_by_user",
            robots_status="allowed_custom",
            terms_status="allowed_custom",
            llm_ingest_allowed=False,
        ),
    ])
    db.commit()

    updated = reconcile_verified_source_profiles(db)
    cbp = db.query(SourceConfig).filter(SourceConfig.id == "cbp").one()
    custom = db.query(SourceConfig).filter(SourceConfig.id == "custom").one()

    assert updated == ["cbp"]
    assert cbp.verification_status == "verified_2026_08_04"
    assert cbp.llm_ingest_allowed is True
    assert cbp.discovery_urls
    assert cbp.crawl_delay_seconds == 2
    assert evaluate_collection_policy(cbp).content_depth == "full"
    assert custom.verification_status == "verified_by_user"
    assert custom.robots_status == "allowed_custom"
    assert custom.llm_ingest_allowed is False
    db.close()


def test_official_api_only_profile_is_allowed_without_web_captcha_bypass():
    source = SourceConfig(
        id="federal-register", name="Federal Register",
        channel=SourceChannel.OFFICIAL,
        base_url="https://www.federalregister.gov/api/v1/documents.json",
        is_active=True, is_configured=True,
        verification_status="legacy_unverified",
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(source)
    db.commit()

    reconcile_verified_source_profiles(db)

    decision = evaluate_collection_policy(source)
    assert decision.automated_fetch_allowed is True
    assert decision.llm_ingest_allowed is True
    assert "API" in source.compliance_note
    db.close()


def test_tavily_profile_allows_api_snippets_but_requires_origin_resolution():
    source = SourceConfig(
        id="tavily", name="Tavily", channel=SourceChannel.API_SEARCH,
        api_key="configured", is_active=True, is_configured=True,
        verification_status="legacy_unverified",
    )
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(source)
    db.commit()

    reconcile_verified_source_profiles(db)

    assert evaluate_collection_policy(source).content_depth == "full"
    assert source.origin_resolution_required is True
    assert "默认不抓全文" in source.compliance_note
    db.close()


def test_known_host_wrong_channel_or_path_is_not_promoted():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        SourceConfig(
            id="cbp-login", name="CBP login", channel=SourceChannel.WEB_SCRAPE,
            base_url="https://www.cbp.gov/user/login", is_active=True,
            is_configured=True, verification_status="legacy_unverified",
        ),
        SourceConfig(
            id="federal-web", name="Federal web", channel=SourceChannel.WEB_SCRAPE,
            base_url="https://www.federalregister.gov/api/v1/documents.json",
            is_active=True, is_configured=True,
            verification_status="legacy_unverified",
        ),
    ])
    db.commit()

    assert reconcile_verified_source_profiles(db) == []
    assert all(
        source.verification_status == "legacy_unverified"
        for source in db.query(SourceConfig).all()
    )
    db.close()


def test_profile_rejects_mismatched_effective_api_address_and_tavily_dispatcher():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add_all([
        SourceConfig(
            id="mismatched-json", name="Mismatched JSON",
            channel=SourceChannel.JSON_API,
            base_url="https://www.gov.uk/api/content/",
            api_endpoint="http://127.0.0.1:8109/metrics",
            is_active=True, is_configured=True,
            verification_status="legacy_unverified",
        ),
        SourceConfig(
            id="tavily", name="Tavily switched to Baidu",
            channel=SourceChannel.API_SEARCH,
            auth_config={"search_type": "baidu_qianfan"},
            api_key="configured", is_active=True, is_configured=True,
            verification_status="legacy_unverified",
        ),
    ])
    db.commit()

    updated = reconcile_verified_source_profiles(db)

    assert updated == []
    assert all(
        source.verification_status == "legacy_unverified"
        for source in db.query(SourceConfig).all()
    )
    db.close()


def test_verified_profile_never_promotes_plain_http_variant():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    db.add(SourceConfig(
        id="cbp-http", name="CBP over HTTP", channel=SourceChannel.WEB_SCRAPE,
        base_url="http://www.cbp.gov/newsroom/media-releases/all",
        is_active=True, is_configured=True,
        verification_status="legacy_unverified",
    ))
    db.commit()

    assert reconcile_verified_source_profiles(db) == []
    assert db.get(SourceConfig, "cbp-http").verification_status == "legacy_unverified"
    db.close()


def test_eu_presscorner_rss_is_verified_for_llm_ingestion():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    source = SourceConfig(
        id="eu-daily-news-rss", name="European Commission Press Corner",
        channel=SourceChannel.RSS,
        base_url="https://ec.europa.eu/commission/presscorner/api/rss?language=en",
        is_active=True, is_configured=True,
        verification_status="legacy_unverified",
    )
    db.add(source)
    db.commit()

    assert reconcile_verified_source_profiles(db) == ["eu-daily-news-rss"]

    db.refresh(source)
    assert source.terms_status == "cc_by_4_0_with_exceptions"
    assert source.llm_ingest_allowed is True
    assert source.languages == ["en", "multi"]
    assert evaluate_collection_policy(source).content_depth == "full"
    db.close()
