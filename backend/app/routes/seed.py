"""Seed default data route."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, ModelConfig, SearchToolConfig, SourceConfig, Tag, Topic
from app.source_taxonomy import determine_source_group
from app.verified_source_catalog import install_verified_global_sources

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["seed"])

_DEFENSE_PROCUREMENT_SOURCE_IDS = {
    "usaspending-dod-awards", "sam-dod-opportunities", "dod-contract-announcements",
    "japan-mod-procurement", "japan-atla-contracts",
    "india-cppp-defense", "india-ddp-procurement",
    "taiwan-pcc-defense-tenders", "taiwan-pcc-defense-awards",
}

_PUBLIC_METADATA_FIELDS = (
    "name", "description", "base_url", "api_endpoint", "homepage_url",
    "default_keywords", "default_categories", "languages", "country_focus",
    "rate_limit_rps", "max_items_per_run", "timeout_seconds", "auth_config",
    "legal_basis", "compliance_note",
)

from ._seed_data import (
    _DEFAULT_CATEGORIES,
    _default_topics,
    _default_search_tools,
    _default_tags,
    _default_keyword_tags,
    _default_description_prompt,
)
from ._seed_sources import (
    _default_sources,
)


@router.post("/seed-defaults")
def seed_defaults(db: Session = Depends(get_db)):
    created_categories = 0
    for cfg in _DEFAULT_CATEGORIES:
        if not db.query(Category).filter(Category.id == cfg["id"]).first():
            db.add(Category(**cfg))
            created_categories += 1

    created_sources = 0
    updated_sources = 0
    for cfg in _default_sources():
        cfg = {**cfg, "source_group": cfg.get("source_group") or determine_source_group(cfg)}
        existing = db.query(SourceConfig).filter(SourceConfig.id == cfg["id"]).first()
        if not db.query(SourceConfig).filter(SourceConfig.id == cfg["id"]).first():
            # Bundled definitions are the only fresh rows allowed to enter the
            # legacy compatibility lane; operator-created/imported rows fail closed.
            db.add(SourceConfig(**{
                **cfg, "verification_status": "legacy_unverified",
            }))
            created_sources += 1
        elif cfg["id"] in _DEFENSE_PROCUREMENT_SOURCE_IDS:
            for field in _PUBLIC_METADATA_FIELDS:
                if field in cfg:
                    setattr(existing, field, cfg[field])
            existing.is_configured = bool(existing.base_url or existing.api_endpoint or existing.homepage_url)
            if not existing.source_group or existing.source_group == "other":
                existing.source_group = cfg["source_group"]
            updated_sources += 1

    created_topics = 0
    for cfg in _default_topics():
        if not db.query(Topic).filter(Topic.id == cfg["id"]).first():
            t = Topic(**cfg)
            t.keyword_tags = _default_keyword_tags(cfg["id"])
            t.description_prompt = _default_description_prompt(cfg["id"])
            db.add(t)
            created_topics += 1

    catalog_result = install_verified_global_sources(db)
    created_sources += len(catalog_result["created"])

    # Model configurations are private user settings. Seeding content must not
    # silently add, replace, or select an AI model.
    created_models = 0

    created_tools = 0
    for cfg in _default_search_tools():
        if not db.query(SearchToolConfig).filter(SearchToolConfig.id == cfg["id"]).first():
            db.add(SearchToolConfig(**cfg))
            created_tools += 1

    created_tags = 0
    for cfg in _default_tags():
        if not db.query(Tag).filter(Tag.id == cfg["id"]).first():
            db.add(Tag(**cfg))
            created_tags += 1

    db.commit()
    return {
        "sources_created": created_sources,
        "sources_updated": updated_sources,
        "topics_created": created_topics,
        "categories_created": created_categories,
        "models_created": created_models,
        "search_tools_created": created_tools,
        "tags_created": created_tags,
    }
