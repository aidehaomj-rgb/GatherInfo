"""Evidence-reviewed official sources that can feed the global weekly pipeline."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.collection_policy import evaluate_collection_policy
from app.models import SourceConfig, Topic
from app.source_profile_registry import reconcile_verified_source_profiles


CATALOG_SOURCE_IDS = (
    "federal-register-trade",
    "federal-register-ita",
    "federal-register-usitc",
    "federal-register-ustr",
    "federal-register-cbp",
    "brazil-receita-rss",
    "abf-newsroom-rss",
    "eu-daily-news-rss",
    "uk-dbt-rss",
    "cbp-rss",
)

SUPERSEDED_SOURCE_REPLACEMENTS = (
    ("brazil-mdic-rss", "brazil-receita-rss"),
    ("cbp-newsroom", "cbp-rss"),
    ("ext-src-060", "abf-newsroom-rss"),
)


def _catalog_configs() -> list[dict]:
    """Return fresh nested objects so callers never mutate shared catalog state."""
    return [
        {
            "id": "federal-register-trade",
            "name": "美国 Federal Register 贸易监管",
            "description": "美国 Federal Register 官方公开 API：关税、贸易救济、进出口与出口管制。",
            "channel": "json_api",
            "homepage_url": "https://www.federalregister.gov/",
            "base_url": "https://www.federalregister.gov/api/v1/",
            "api_endpoint": "documents.json",
            "auth_config": {
                "auth": "none",
                "items_path": "results",
                "prefer_default_keywords": True,
                "keyword_param": "conditions[term]",
                "keyword_join": " OR ",
                "query": {"per_page": 100, "order": "newest"},
                "window_start_param": "conditions[publication_date][gte]",
                "window_end_param": "conditions[publication_date][lte]",
                "fields": {
                    "title": "title", "content": "abstract",
                    "summary": "excerpts", "url": "html_url",
                    "published_at": "publication_date", "category": "type",
                },
            },
            "default_keywords": [
                "tariff", "customs", "import", "export control",
            ],
            "default_categories": ["trade", "regulation", "export_control"],
            "languages": ["en"], "country_focus": ["US"],
            "rate_limit_rps": 0.5, "max_items_per_run": 40,
            "timeout_seconds": 30, "is_active": True, "is_configured": True,
            "legal_basis": "FederalRegister.gov public API and U.S. government publications",
        },
        _federal_agency_config(
            "federal-register-ita", "美国国际贸易管理局 Federal Register",
            "international-trade-administration",
            "美国 ITA 贸易救济、反倾销与反补贴决定。",
        ),
        _federal_agency_config(
            "federal-register-usitc", "美国国际贸易委员会 Federal Register",
            "international-trade-commission",
            "美国 USITC 337 调查、产业损害与贸易救济决定。",
        ),
        _federal_agency_config(
            "federal-register-ustr", "美国贸易代表办公室 Federal Register",
            "trade-representative-office-of-united-states",
            "美国 USTR 301 调查、关税行动与贸易政策公告。",
        ),
        _federal_agency_config(
            "federal-register-cbp", "美国海关与边境保护局 Federal Register",
            "u-s-customs-and-border-protection",
            "美国 CBP 通关、费用、申报试点与海关监管公告。",
        ),
        {
            "id": "brazil-receita-rss",
            "name": "巴西 Receita Federal 官方新闻",
            "description": "巴西联邦税务局官方 RSS 1.0，覆盖海关监管、反走私和进口通关。",
            "channel": "rss",
            "homepage_url": "https://www.gov.br/receitafederal/pt-br/assuntos/noticias",
            "base_url": "https://www.gov.br/receitafederal/pt-br/assuntos/noticias/RSS",
            "auth_config": {"defer_keyword_filter_to_llm": True},
            "default_keywords": ["aduana", "importação", "contrabando", "comércio exterior"],
            "default_categories": ["customs", "enforcement", "trade"],
            "languages": ["pt"], "country_focus": ["BR"],
            "rate_limit_rps": 0.5, "max_items_per_run": 40,
            "timeout_seconds": 30, "is_active": True, "is_configured": True,
            "legal_basis": "Brazilian government public RSS",
        },
        {
            "id": "abf-newsroom-rss",
            "name": "澳大利亚边防局 Newsroom RSS",
            "description": "Australian Border Force 官方 Newsroom RSS，覆盖边境执法、查获和贸易合规。",
            "channel": "rss",
            "homepage_url": "https://www.abf.gov.au/newsroom-subsite/Pages/default.aspx",
            "base_url": "https://www.abf.gov.au/_layouts/15/AppPages/Rss.aspx?site=newsroom",
            "auth_config": {"defer_keyword_filter_to_llm": True},
            "default_keywords": ["border", "customs", "seizure", "trade compliance"],
            "default_categories": ["customs", "enforcement", "trade"],
            "languages": ["en"], "country_focus": ["AU"],
            "rate_limit_rps": 0.2, "max_items_per_run": 30,
            "timeout_seconds": 30, "is_active": True, "is_configured": True,
            "legal_basis": "Australian government public RSS",
        },
        {
            "id": "eu-daily-news-rss",
            "name": "欧盟委员会 Press Corner 官方 RSS",
            "description": "European Commission 官方发布流，覆盖贸易、关税、制裁与监管政策。",
            "channel": "rss",
            "homepage_url": "https://ec.europa.eu/commission/presscorner/",
            "base_url": (
                "https://ec.europa.eu/commission/presscorner/api/rss?language=en"
            ),
            "auth_config": {
                "defer_keyword_filter_to_llm": True,
                "follow_item_links": True,
                "item_path_prefixes": ["/commission/presscorner/detail/"],
                "detail_fetch_strategy": "eu_presscorner_api",
                "detail_api_endpoint": (
                    "https://ec.europa.eu/commission/presscorner/api/documents"
                ),
                "max_detail_items": 6,
                "min_detail_content_chars": 800,
                "max_detail_content_chars": 30_000,
            },
            "default_keywords": [
                "trade", "customs", "tariff", "sanctions", "export control",
                "anti-dumping", "foreign subsidies",
            ],
            "default_categories": [
                "trade", "regulation", "sanctions", "export_control",
            ],
            "languages": ["en"], "country_focus": ["EU"],
            "rate_limit_rps": 0.5, "max_items_per_run": 20,
            "timeout_seconds": 30, "is_active": True, "is_configured": True,
            "legal_basis": (
                "European Commission legal notice: Commission-owned text is "
                "reusable under CC BY 4.0 with stated exceptions"
            ),
        },
        {
            "id": "uk-dbt-rss",
            "name": "英国商业与贸易部官方 Atom",
            "description": "UK Department for Business and Trade 官方发布流，覆盖贸易政策、制裁和出口管制。",
            "channel": "rss",
            "homepage_url": (
                "https://www.gov.uk/government/organisations/"
                "department-for-business-and-trade"
            ),
            "base_url": (
                "https://www.gov.uk/government/organisations/"
                "department-for-business-and-trade.atom"
            ),
            "auth_config": {"defer_keyword_filter_to_llm": True},
            "default_keywords": [
                "trade policy", "tariff", "sanctions", "export control",
                "trade remedy", "customs",
            ],
            "default_categories": [
                "trade", "sanctions", "export_control", "regulation",
            ],
            "languages": ["en"], "country_focus": ["GB"],
            "rate_limit_rps": 1.0, "max_items_per_run": 30,
            "timeout_seconds": 30, "is_active": True, "is_configured": True,
            "legal_basis": "UK Open Government Licence with stated exceptions",
        },
        {
            "id": "cbp-rss",
            "name": "美国 CBP Newsroom 官方 RSS",
            "description": "U.S. Customs and Border Protection 官方新闻流，覆盖海关执法、通关和贸易合规。",
            "channel": "rss",
            "homepage_url": "https://www.cbp.gov/newsroom",
            "base_url": "https://www.cbp.gov/rss/newsroom",
            "auth_config": {"defer_keyword_filter_to_llm": True},
            "default_keywords": [
                "customs", "trade enforcement", "import", "export",
                "forced labor", "seizure",
            ],
            "default_categories": ["customs", "enforcement", "trade"],
            "languages": ["en"], "country_focus": ["US"],
            "rate_limit_rps": 0.5, "max_items_per_run": 30,
            "timeout_seconds": 30, "is_active": True, "is_configured": True,
            "legal_basis": "U.S. government public-domain content with stated exceptions",
        },
    ]


def _federal_agency_config(
    source_id: str,
    name: str,
    agency_slug: str,
    description: str,
) -> dict:
    return {
        "id": source_id, "name": name, "description": description,
        "channel": "json_api",
        "homepage_url": "https://www.federalregister.gov/",
        "base_url": "https://www.federalregister.gov/api/v1/",
        "api_endpoint": "documents.json",
        "auth_config": {
            "auth": "none", "items_path": "results",
            "query": {
                "per_page": 100, "order": "newest",
                "conditions[agencies][]": agency_slug,
            },
            "window_start_param": "conditions[publication_date][gte]",
            "window_end_param": "conditions[publication_date][lte]",
            "fields": {
                "title": "title", "content": "abstract",
                "summary": "excerpts", "url": "html_url",
                "published_at": "publication_date", "category": "type",
            },
        },
        "default_keywords": [],
        "default_categories": ["trade", "regulation", "export_control"],
        "languages": ["en"], "country_focus": ["US"],
        "rate_limit_rps": 0.5, "max_items_per_run": 40,
        "timeout_seconds": 30, "is_active": True, "is_configured": True,
        "legal_basis": "FederalRegister.gov public API and U.S. government publications",
    }


def install_verified_global_sources(
    db: Session,
    *,
    topic_id: str = "global-trade",
    refresh_managed: bool = False,
) -> dict[str, list[str]]:
    """Create missing catalog rows, verify them, and bind eligible rows once."""
    created: list[str] = []
    refreshed: list[str] = []
    for config in _catalog_configs():
        source_id = str(config["id"])
        existing = db.get(SourceConfig, source_id)
        if existing is not None and not refresh_managed:
            continue
        if existing is None:
            db.add(SourceConfig(**{
                **config,
                "verification_status": "legacy_unverified",
            }))
            created = [*created, source_id]
            continue
        update_values = {
            **{key: value for key, value in config.items() if key != "id"},
            "verification_status": "legacy_unverified",
            "robots_status": "unverified",
            "terms_status": "unverified",
            "llm_ingest_allowed": False,
            "verified_at": None,
        }
        db.query(SourceConfig).filter(SourceConfig.id == source_id).update(
            update_values, synchronize_session=False,
        )
        refreshed = [*refreshed, source_id]
    db.flush()
    if refreshed:
        db.expire_all()

    reconciled = reconcile_verified_source_profiles(db)
    verified = [source_id for source_id in CATALOG_SOURCE_IDS if source_id in reconciled]
    deactivated = _deactivate_superseded_sources(db)
    topic = db.get(Topic, topic_id)
    bound: list[str] = []
    if topic is not None:
        current_ids = [
            str(source_id) for source_id in (topic.source_ids or []) if source_id
        ]
        additions = []
        for source_id in CATALOG_SOURCE_IDS:
            source = db.get(SourceConfig, source_id)
            if source is None or source_id in current_ids:
                continue
            if evaluate_collection_policy(source).content_depth != "full":
                continue
            additions = [*additions, source_id]
        if additions:
            topic.source_ids = [*current_ids, *additions]
            bound = [*additions]
    db.commit()
    return {
        "created": created, "refreshed": refreshed,
        "verified": verified, "bound": bound,
        "deactivated": deactivated,
    }


def _deactivate_superseded_sources(db: Session) -> list[str]:
    deactivated: list[str] = []
    for source_id, replacement_id in SUPERSEDED_SOURCE_REPLACEMENTS:
        source = db.get(SourceConfig, source_id)
        if source is None or not source.is_active:
            continue
        source.is_active = False
        message = (
            f"该旧连接器已由受管官方源 {replacement_id} 替代；保留历史定义，"
            "避免重复采集或持续失败。"
        )
        previous = str(source.compliance_note or "").strip()
        source.compliance_note = (
            previous if message in previous
            else "\n".join(value for value in (previous, message) if value)
        )
        deactivated = [*deactivated, source_id]
    return deactivated


__all__ = [
    "CATALOG_SOURCE_IDS", "SUPERSEDED_SOURCE_REPLACEMENTS",
    "install_verified_global_sources",
]
