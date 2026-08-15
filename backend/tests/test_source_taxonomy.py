"""Pure-function tests for the information-source business taxonomy."""

from pathlib import Path
from types import SimpleNamespace
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.source_taxonomy import (  # noqa: E402
    SOURCE_GROUPS,
    SOURCE_GROUP_CODES,
    backfill_source_groups,
    determine_source_group,
)


def test_taxonomy_defines_thirteen_unique_complete_groups():
    assert len(SOURCE_GROUPS) == 13
    assert len(SOURCE_GROUP_CODES) == 13
    assert SOURCE_GROUP_CODES == {group.code for group in SOURCE_GROUPS}
    assert all(group.name and group.description for group in SOURCE_GROUPS)


def test_default_seed_sources_have_valid_business_groups():
    from app.routes._seed_sources import _default_sources

    sources = _default_sources()
    assert sources
    assert all(source.get("source_group") in SOURCE_GROUP_CODES for source in sources)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        (
            {"id": "wto-news", "name": "WTO News", "homepage_url": "https://www.wto.org"},
            "government_igo",
        ),
        (
            {"id": "ofac", "name": "OFAC Sanctions", "homepage_url": "https://ofac.treasury.gov"},
            "regulation_trade_measures",
        ),
        (
            {"id": "cbp", "name": "CBP Customs Seizures", "homepage_url": "https://www.cbp.gov"},
            "customs_enforcement",
        ),
        (
            {
                "id": "sam-dod",
                "name": "SAM.gov opportunities",
                "default_categories": ["defense_procurement", "opportunity"],
            },
            "procurement_opportunity",
        ),
        (
            {"id": "comtrade", "name": "UN Comtrade 全球贸易数据库"},
            "trade_commodity_data",
        ),
        (
            {"id": "zim", "name": "ZIM 航线与服务更新"},
            "supply_chain_company",
        ),
        (
            {"id": "reuters", "name": "Reuters Asia Pacific"},
            "news_risk_media",
        ),
        (
            {"id": "reddit-trade", "name": "Reddit International Trade"},
            "community_social",
        ),
        (
            {"id": "tavily", "name": "Tavily Web Search", "api_endpoint": "https://api.tavily.com"},
            "search_aggregation",
        ),
    ],
)
def test_representative_sources_cover_every_group(source, expected):
    result = determine_source_group(source)
    assert result == expected
    assert result in SOURCE_GROUP_CODES


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        # Specific functions win over a generic official/government host.
        (
            {
                "id": "sam-dod",
                "name": "US federal procurement",
                "homepage_url": "https://sam.gov",
                "default_categories": '["defense_procurement"]',
            },
            "procurement_opportunity",
        ),
        (
            {
                "id": "cbp-news",
                "name": "CBP Newsroom",
                "homepage_url": "https://www.cbp.gov",
                "default_categories": '["official-policy"]',
            },
            "customs_enforcement",
        ),
        (
            {
                "id": "newsapi",
                "name": "NewsAPI",
                "default_categories": '["commercial-data", "data-api"]',
            },
            "search_aggregation",
        ),
        # A reviewed source ID wins over broad name matching.
        (
            {"id": "ext-source-217", "name": "陈俊杰律师团队"},
            "regulation_trade_measures",
        ),
        # Object attributes are supported in addition to mappings.
        (
            SimpleNamespace(id="community", name="LinkedIn 外贸行业群组"),
            "community_social",
        ),
    ],
)
def test_first_match_precedence_overrides_and_source_shapes(source, expected):
    assert determine_source_group(source) == expected


def test_unmatched_source_falls_back_to_news_media():
    assert determine_source_group({"id": "unknown", "name": "Regional Daily"}) == "news_risk_media"


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ({"id": "case-news", "name": "Border case", "default_categories": ["news-enforcement"]},
         "enforcement_risk_media"),
        ({"id": "hotspot", "name": "Regional update", "default_categories": ["news-hotspots"]},
         "regional_hotspot_media"),
        ({"id": "trade-daily", "name": "Global Trade News", "default_categories": ["trade"]},
         "trade_industry_media"),
        ({"id": "policy-lab", "name": "International Policy Research Institute"},
         "research_thinktank"),
    ],
)
def test_news_media_subgroups(source, expected):
    assert determine_source_group(source) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ({"description": "InfoRoute import: embassy.example (official_government)"},
         "government_igo"),
        ({"base_url": "https://facebook.com/post/1",
          "description": "InfoRoute import: facebook.com (social_platform)"},
         "community_social"),
        ({"base_url": "https://kwtx.com/news/1",
          "description": "InfoRoute import: kwtx.com (social_platform)"},
         "news_risk_media"),
    ],
)
def test_inforoute_reviewed_source_type(source, expected):
    assert determine_source_group({
        "id": "inforoute-source", "name": "Generic", **source,
    }) == expected


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ({"id": "abc", "name": "ABC News", "base_url": "https://abcnews.go.com",
          "description": "InfoRoute import: abcnews.go.com (official_government)"},
         "news_risk_media"),
        ({"id": "indonesia-police", "name": "Tribrata News",
          "base_url": "https://tribratanews.polri.go.id"}, "customs_enforcement"),
        ({"id": "wipo-lex", "name": "WIPO Lex", "base_url": "https://wipo.int/wipolex"},
         "regulation_trade_measures"),
        ({"id": "cme", "name": "CME Group", "base_url": "https://cmegroup.com"},
         "trade_commodity_data"),
        ({"id": "universal-logistics", "name": "Universal Logistics",
          "base_url": "https://universallogistics.com"}, "supply_chain_company"),
        ({"id": "feedly", "name": "Feedly 情报源", "base_url": "https://cloud.feedly.com/v3"},
         "search_aggregation"),
        ({"id": "croatia-customs", "name": "Carina",
          "base_url": "https://carina.gov.hr/news"}, "customs_enforcement"),
        ({"id": "farm-health", "name": "农业农村部 - 疫情发布",
          "base_url": "https://xmsyj.moa.gov.cn/yqfb"}, "government_igo"),
        ({"id": "local-tv", "name": "WTOC", "base_url": "https://wtoc.com/news"},
         "news_risk_media"),
        ({"id": "simfruit", "name": "Simfruit", "base_url": "https://simfruit.cl"},
         "news_risk_media"),
        ({"id": "govdelivery", "name": "CBP bulletin",
          "base_url": "https://content.govdelivery.com/accounts/USDHSCBP/bulletins/1"},
         "customs_enforcement"),
    ],
)
def test_inventory_precision_rules(source, expected):
    assert determine_source_group(source) == expected


def test_backfill_replaces_legacy_other_but_keeps_curated_group(tmp_path):
    from sqlalchemy import create_engine, text

    engine = create_engine(f"sqlite:///{tmp_path / 'groups.db'}")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE source_configs (
                id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT,
                base_url TEXT, api_endpoint TEXT, homepage_url TEXT,
                default_categories JSON, source_group TEXT
            )
        """))
        connection.execute(text("""
            INSERT INTO source_configs (id, name, source_group) VALUES
            ('regional', 'Regional Daily', 'other'),
            ('curated', 'Regional Daily', 'government_igo')
        """))
        assert backfill_source_groups(connection) == 1
        assert backfill_source_groups(connection) == 0
        groups = dict(connection.execute(text(
            "SELECT id, source_group FROM source_configs"
        )).all())
    assert groups == {
        "regional": "news_risk_media",
        "curated": "government_igo",
    }
