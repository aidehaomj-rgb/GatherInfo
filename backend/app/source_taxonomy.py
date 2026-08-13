"""Business taxonomy for information sources.

``SourceConfig.channel`` selects a collector implementation.  It must not be
used as a business category.  The functions in this module assign the separate
``source_group`` dimension without changing channel or topic tags.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import json
from typing import Any
import urllib.parse

from sqlalchemy import text


@dataclass(frozen=True, slots=True)
class SourceGroupDefinition:
    code: str
    name: str
    description: str


SOURCE_GROUPS: tuple[SourceGroupDefinition, ...] = (
    SourceGroupDefinition(
        "government_igo",
        "政府与国际组织",
        "政府部门、驻外机构及国际组织的一般公告和政策动态。",
    ),
    SourceGroupDefinition(
        "regulation_trade_measures",
        "法规政策与贸易措施",
        "出口管制、制裁、贸易救济、关税以及 TBT/SPS 等规则信息。",
    ),
    SourceGroupDefinition(
        "customs_enforcement",
        "海关执法与通关合规",
        "海关公告、查缉执法、报关清关和关务合规信息。",
    ),
    SourceGroupDefinition(
        "procurement_opportunity",
        "采购招标与供应商机会",
        "政府及防务采购公告、中标合同与供应商机会。",
    ),
    SourceGroupDefinition(
        "trade_commodity_data",
        "贸易数据与商品市场",
        "贸易统计、宏观数据库、商品价格和关键矿产数据。",
    ),
    SourceGroupDefinition(
        "supply_chain_company",
        "供应链物流与企业动态",
        "航运、货代、物流、运输服务和企业经营动态。",
    ),
    SourceGroupDefinition(
        "news_risk_media",
        "综合新闻媒体",
        "通讯社、综合新闻门户及无法进一步细分的公开媒体来源。",
    ),
    SourceGroupDefinition(
        "trade_industry_media",
        "贸易与行业媒体",
        "聚焦国际贸易、航运物流、产业和企业动态的专业媒体。",
    ),
    SourceGroupDefinition(
        "enforcement_risk_media",
        "执法案件与风险事件",
        "执法查获、走私案件、跨境犯罪及合规风险事件报道。",
    ),
    SourceGroupDefinition(
        "regional_hotspot_media",
        "地区热点媒体",
        "按国家和地区跟踪政经热点、突发事件与区域风险的媒体。",
    ),
    SourceGroupDefinition(
        "research_thinktank",
        "研究机构与智库",
        "智库、大学、研究机构及专业政策分析来源。",
    ),
    SourceGroupDefinition(
        "community_social",
        "行业社区与社会线索",
        "论坛、社交平台和行业社区中的一手线索。",
    ),
    SourceGroupDefinition(
        "search_aggregation",
        "搜索与聚合工具",
        "搜索 API、新闻聚合器、RSS 生成和情报检索工具。",
    ),
)

SOURCE_GROUP_BY_CODE = {group.code: group for group in SOURCE_GROUPS}
SOURCE_GROUP_CODES = frozenset(SOURCE_GROUP_BY_CODE)
SOURCE_GROUP_INPUT_CODES = SOURCE_GROUP_CODES | {"other"}


# Stable IDs record deliberately reviewed exceptions where broad metadata or a
# provider-supplied label is known to be misleading.  Keeping these decisions
# here makes a full reclassification deterministic and auditable.
SOURCE_GROUP_OVERRIDES: dict[str, str] = {
    "ext-cpec-222": "government_igo",
    "ext-usy-208": "news_risk_media",
    "ext-source-203": "news_risk_media",
    "ext-source-204": "news_risk_media",
    "ext-source-205": "news_risk_media",
    "ext-source-207": "government_igo",
    "ext-source-209": "supply_chain_company",
    "ext-source-210": "news_risk_media",
    "ext-source-211": "news_risk_media",
    "ext-source-212": "news_risk_media",
    "ext-source-213": "supply_chain_company",
    "ext-source-214": "news_risk_media",
    "ext-source-215": "news_risk_media",
    "ext-source-217": "regulation_trade_measures",
    "ext-source-218": "news_risk_media",
    "ext-source-220": "regulation_trade_measures",
    "ext-source-223": "news_risk_media",
    "ext-source-224": "news_risk_media",
    "ext-source-225": "news_risk_media",
    "ext-source-226": "trade_commodity_data",
    "ext-source-227": "regulation_trade_measures",
    "ext-source-229": "trade_commodity_data",
    "ext-source-230": "supply_chain_company",
    "ext-source-231": "news_risk_media",
    "ext-source-232": "supply_chain_company",
    "ext-source-233": "news_risk_media",
    "ext-source-234": "news_risk_media",
    "ext-source-236": "news_risk_media",
    "ext-source-237": "news_risk_media",
    "ext-source-240": "news_risk_media",
    "ext-source-241": "news_risk_media",
    "ext-source-242": "news_risk_media",
    "ext-source-243": "government_igo",
    "ext-source-244": "news_risk_media",
    "ext-source-245": "government_igo",
    "ext-source-246": "news_risk_media",
    "ext-source-247": "news_risk_media",
    "ext-source-248": "news_risk_media",
    "ext-source-249": "news_risk_media",
    "ext-source-250": "news_risk_media",
    # Reviewed false positives from the combined 2026-08-11 inventory.
    "baltic-exchange": "trade_commodity_data",
    "brazil-mdic-rss": "regulation_trade_measures",
    "csis-rss": "news_risk_media",
    "eaeu-rss": "regulation_trade_measures",
    "eu-critical-raw-materials-act": "regulation_trade_measures",
    "eu-trade-helpdesk": "regulation_trade_measures",
    "eu-trade-rss": "regulation_trade_measures",
    "ext-ecoscope-archives-056": "news_risk_media",
    "ext-foreign-trade-193": "news_risk_media",
    "ext-legal-industry-186": "news_risk_media",
    "ext-media-releases-060": "customs_enforcement",
    "ext-news-054": "customs_enforcement",
    "ext-source-139": "government_igo",
    "ext-source-151": "news_risk_media",
    "ext-source-160": "news_risk_media",
    "ext-source-170": "news_risk_media",
    "ext-tariffs-159": "news_risk_media",
    "ext-vietnam-vn-ministry-of-industry-and-trade-049": "news_risk_media",
    "globaltradealert-rss": "regulation_trade_measures",
    "gta-rss": "regulation_trade_measures",
    "hotspot-wtoc-com-154": "news_risk_media",
    "iisd-rss": "news_risk_media",
    "india-dgft-rss": "regulation_trade_measures",
    "inforoute-063ec658c9ff": "customs_enforcement",
    "inforoute-07957963adb8": "supply_chain_company",
    "inforoute-1142ba1b9b7d": "supply_chain_company",
    "inforoute-1bbf598eb027": "news_risk_media",
    "inforoute-28caeb439121": "news_risk_media",
    "inforoute-4b0a5dc54c53": "regulation_trade_measures",
    "inforoute-4ed7051c86ce": "customs_enforcement",
    "inforoute-48cd9ddb5bc0": "news_risk_media",
    "inforoute-5e36ac2fa232": "supply_chain_company",
    "inforoute-61622303bba1": "trade_commodity_data",
    "inforoute-6353a51615fd": "trade_commodity_data",
    "inforoute-85452b634a6a": "customs_enforcement",
    "inforoute-8cfa5623e7f3": "customs_enforcement",
    "inforoute-aae603cf56dd": "customs_enforcement",
    "inforoute-c36c93b614d6": "regulation_trade_measures",
    "inforoute-ce20145b17f4": "news_risk_media",
    "inforoute-df209d8d2f22": "customs_enforcement",
    "inforoute-e95342504abe": "customs_enforcement",
    "inforoute-fdd81573782e": "news_risk_media",
    "iea-rss": "trade_commodity_data",
    "nvoccs-registry": "supply_chain_company",
    "olaf": "customs_enforcement",
    "piie-rss": "news_risk_media",
    "turkey-trade-rss": "regulation_trade_measures",
    "tw-newtalk": "news_risk_media",
    "uk-trade-remedies-rss": "regulation_trade_measures",
    "un-news-rss": "news_risk_media",
    "usda-fas-rss": "trade_commodity_data",
    "web-hc23-transport-directory": "supply_chain_company",
    "web-jinxiu-logistics": "supply_chain_company",
    "web-linktrans-official": "supply_chain_company",
    "web-welisen-logistics": "supply_chain_company",
    "web-zerrand-crossborder-runner": "supply_chain_company",
    "weekly-au-afp": "customs_enforcement",
    "weekly-br-receita-federal": "customs_enforcement",
    "worldbank-blog-rss": "news_risk_media",
    "worldbank-commodity-markets": "trade_commodity_data",
    "yict-vessel-schedule": "supply_chain_company",
    "zim-service-updates": "supply_chain_company",
}


_SEARCH_MARKERS = (
    "search-ai", "search-api", "api.tavily.com", "tavily web search",
    "tavily web 搜索", "cloud.feedly.com", "feedly 情报源", "cloud.baidu.com",
    "search1api", "bing-search", "google-alerts", "rss.app", "newsapi",
    "inoreader",
)
_COMMUNITY_MARKERS = (
    "reddit", "论坛", "群组", "forum", "tieba", "linkedin", "community",
    "社区", "外贸论坛", "风险原帖", "facebook.com", "toutiao.com",
    "mp.weixin.qq.com",
)
_PROCUREMENT_MARKERS = (
    "defense_procurement", "procurement_notice", "contract_award",
    "sam.gov", "usaspending", "防务采购", "国防合同", "每日合同公告",
)
_REGULATION_MARKERS = (
    "export-control-sanctions", "trade-remedy-tariff", "tbt-sps-regulation",
    "sanctions", "trade-remedy", "tariff", "出口管制", "贸易救济",
    "eping", "eur-lex", "ofac", "bis export", "dof.gob.mx",
    "journaloftradingstandards.co.uk", "wipo lex", "法规", "政策发布",
    "global trade alert", "trb.mofcom.gov.cn", "chinawto.mofcom.gov.cn",
)
_CUSTOMS_MARKERS = (
    "customs-enforcement", "海关", "customs", "清关", "缉私",
    "关务合规", "wco", "cbp", "beacukai", "aduana", "douane",
    "zoll.de", "tullverket.se", "tulli.fi", "ana.gob.pa", "polri.go.id",
    "carina.gov.hr", "ice.gov", "abf.gov.au", "border force",
)
_DATA_MARKERS = (
    "comtrade", "world bank open data", "trademap", "commodity prices",
    "food price index", "mineral commodity", "smm稀土", "argusmetals",
    "data-api", "commercial-data", "cme group",
    "cmegroup.com", "lbma.org.uk", "opec basket", "trading economics",
    "tradingeconomics.com", "s&p global market intelligence",
)
_SUPPLY_CHAIN_MARKERS = (
    "物流", "货代", "航运", "航线", "运输", "supply chain", "supplychain",
    "shipping", "maritime", "container", "trade winds", "tradewinds",
    "universallogistics.com",
)
_GOVERNMENT_MARKERS = (
    "政府", "商务部", "外交部", "农业农村部", "使馆",
    "委员会", "commission", "ministry", "wto.org", "world trade organization",
    "unctad", "oecd", "imf.org", "international monetary fund",
    "worldbank", "world bank", "adb.org", "asian development bank",
    "asean.org", "europa.eu", "ustr.gov",
    "dfat.gov", "mfat.gov", "international.gc.ca", "meti.go.jp", "fao.org",
    "iea.org", "usda", "usitc", "whitehouse",
)

_RESEARCH_MARKERS = (
    "think tank", "thinktank", "research institute", "policy institute",
    "研究院", "研究所", "研究中心", "智库", "大学", "university",
    "csis", "piie", "iisd", "brookings", "chatham house",
    "carnegie", "rand corporation", "council on foreign relations",
)
_ENFORCEMENT_NEWS_CATEGORIES = {
    "news-enforcement", "网页·执法信息", "enforcement", "crime",
}
_HOTSPOT_NEWS_CATEGORIES = {
    "news-hotspots", "网页·热点信息", "historical-360",
}
_TRADE_MEDIA_MARKERS = (
    "trade news", "trade media", "贸易新闻", "外贸", "财经", "finance",
    "business news", "shipping news", "maritime news", "物流媒体",
    "航运媒体", "行业媒体", "industry news", "commodity news",
)


def _value(source: Any, field: str) -> Any:
    if isinstance(source, Mapping):
        return source.get(field)
    value = getattr(source, field, None)
    if value is not None:
        return value
    try:
        return source[field]
    except (KeyError, IndexError, TypeError):
        return None


def _list_value(value: Any) -> list[str]:
    if not value:
        return []
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return [value]
        value = decoded
    if isinstance(value, (list, tuple, set)):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _searchable_text(source: Any) -> str:
    parts = [str(_value(source, field) or "") for field in ("id", "name")]
    for field in ("homepage_url", "base_url", "api_endpoint"):
        url = _value(source, field)
        if url:
            parts.append(urllib.parse.urlparse(str(url)).hostname or "")
            break
    parts.extend(_list_value(_value(source, "default_categories")))
    return " ".join(parts).casefold()


def _source_hosts(source: Any) -> tuple[str, ...]:
    hosts: list[str] = []
    for field in ("homepage_url", "base_url", "api_endpoint"):
        value = str(_value(source, field) or "").strip()
        if not value:
            continue
        parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
        if parsed.hostname:
            hosts.append(parsed.hostname.casefold())
    return tuple(dict.fromkeys(hosts))


def _has_government_host(source: Any) -> bool:
    """Recognise government host labels without matching ``govdelivery.com``."""
    return any(
        label in {"gov", "gouv", "gob", "govt"}
        for host in _source_hosts(source)
        for label in host.split(".")
    )


def _contains_any(text_value: str, markers: tuple[str, ...]) -> bool:
    return any(marker.casefold() in text_value for marker in markers)


def determine_source_group(source: Any) -> str:
    """Return one mutually exclusive business group for a source-like object.

    ``source`` can be a mapping, SQLAlchemy row/model, dataclass or any object
    exposing SourceConfig-like attributes.  Rules are deliberately first-match:
    specific source functions precede the general government/media fallbacks.
    """
    source_id = str(_value(source, "id") or "").casefold()
    reviewed_group = SOURCE_GROUP_OVERRIDES.get(source_id)
    if reviewed_group and reviewed_group != "news_risk_media":
        return reviewed_group

    source_text = _searchable_text(source)
    description = str(_value(source, "description") or "").casefold()
    categories = {
        value.casefold() for value in _list_value(
            _value(source, "default_categories")
        )
    }
    if categories.intersection(_ENFORCEMENT_NEWS_CATEGORIES):
        return "enforcement_risk_media"
    if categories.intersection(_HOTSPOT_NEWS_CATEGORIES):
        return "regional_hotspot_media"
    # The provider type is useful only when its domain is itself a recognised
    # social platform; several ordinary news/company sites were mislabeled.
    if "social_platform" in description and _contains_any(
        source_text, _COMMUNITY_MARKERS
    ):
        return "community_social"
    rules = (
        ("search_aggregation", _SEARCH_MARKERS),
        ("community_social", _COMMUNITY_MARKERS),
        ("procurement_opportunity", _PROCUREMENT_MARKERS),
        ("regulation_trade_measures", _REGULATION_MARKERS),
        ("customs_enforcement", _CUSTOMS_MARKERS),
        ("trade_commodity_data", _DATA_MARKERS),
        ("supply_chain_company", _SUPPLY_CHAIN_MARKERS),
    )
    for group_code, markers in rules:
        if _contains_any(source_text, markers):
            return group_code
    if "price" in categories and categories.intersection(
        {"futures", "metal", "energy", "commodity", "shipping"}
    ):
        return "trade_commodity_data"
    if "信息源分类: 新闻媒体" in description or "(news_media)" in description:
        if _contains_any(source_text, _RESEARCH_MARKERS):
            return "research_thinktank"
        if _contains_any(source_text, _TRADE_MEDIA_MARKERS):
            return "trade_industry_media"
        return "news_risk_media"
    if _contains_any(source_text, _GOVERNMENT_MARKERS) or _has_government_host(source):
        return "government_igo"
    if "official_government" in description and "abcnews.go.com" not in source_text:
        return "government_igo"
    if "official-policy" in categories:
        return "government_igo"
    if _contains_any(source_text, _RESEARCH_MARKERS):
        return "research_thinktank"
    if _contains_any(source_text, _TRADE_MEDIA_MARKERS):
        return "trade_industry_media"
    return "news_risk_media"


def backfill_source_groups(
    connection: Any,
    *,
    available_columns: set[str] | None = None,
    replace_other: bool = True,
) -> int:
    """Fill unclassified ``source_group`` values using an existing connection.

    The caller must add the column before invoking this helper and owns the
    transaction.  Existing curated groups are never overwritten.  ``other`` is
    considered the legacy migration default by default, allowing an upgraded
    database to receive the taxonomy once; subsequent calls are idempotent.
    """
    missing_predicate = (
        "source_group IS NULL OR TRIM(source_group) = '' OR source_group = 'other'"
        if replace_other
        else "source_group IS NULL OR TRIM(source_group) = ''"
    )
    optional_fields = (
        "description", "base_url", "api_endpoint", "homepage_url",
        "default_categories",
    )
    selected_fields = ["id", "name"]
    if available_columns is None:
        selected_fields.extend(optional_fields)
    else:
        selected_fields.extend(
            field for field in optional_fields if field in available_columns
        )
    rows = connection.execute(text("""
        SELECT {selected_fields}
        FROM source_configs
        WHERE {missing_predicate}
    """.format(
        selected_fields=", ".join(selected_fields),
        missing_predicate=missing_predicate,
    ))).mappings().all()
    updates = [
        {"source_id": row["id"], "source_group": determine_source_group(row)}
        for row in rows
    ]
    if updates:
        connection.execute(text("""
            UPDATE source_configs
            SET source_group = :source_group
            WHERE id = :source_id
              AND ({missing_predicate})
        """.format(missing_predicate=missing_predicate)), updates)
    return len(updates)
