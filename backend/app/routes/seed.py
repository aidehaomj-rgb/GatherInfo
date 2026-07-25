"""Seed default data route."""
import logging

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, ModelConfig, SearchToolConfig, SourceConfig, Tag, Topic

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["seed"])

from ._seed_data import (
    _DEFAULT_CATEGORIES,
    _default_topics,
    _default_models,
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
    for cfg in _default_sources():
        if not db.query(SourceConfig).filter(SourceConfig.id == cfg["id"]).first():
            db.add(SourceConfig(**cfg))
            created_sources += 1

    created_topics = 0
    for cfg in _default_topics():
        if not db.query(Topic).filter(Topic.id == cfg["id"]).first():
            t = Topic(**cfg)
            t.keyword_tags = _default_keyword_tags(cfg["id"])
            t.description_prompt = _default_description_prompt(cfg["id"])
            db.add(t)
            created_topics += 1

    created_models = 0
    for cfg in _default_models():
        if not db.query(ModelConfig).filter(ModelConfig.id == cfg["id"]).first():
            db.add(ModelConfig(**cfg))
            created_models += 1

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
        "topics_created": created_topics,
        "categories_created": created_categories,
        "models_created": created_models,
        "search_tools_created": created_tools,
        "tags_created": created_tags,
    }
