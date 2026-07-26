"""Stats, System Settings, Config Export/Import."""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.collection_schemas import (
    StatsOut, SystemConfigOut, SystemConfigUpdate,
)
from app.database import get_db
from app.models import (
    CollectedItem, CollectionRun, ModelConfig,
    ScheduleConfig, SearchToolConfig, SourceConfig,
    SystemConfig, Tag, Topic,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["settings"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _get_system_config(db: Session) -> SystemConfig:
    cfg = db.query(SystemConfig).filter(SystemConfig.id == "global").first()
    if not cfg:
        cfg = SystemConfig(id="global")
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg

# ── Stats ───────────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    today = _now().replace(hour=0, minute=0, second=0, microsecond=0)
    last = db.query(CollectedItem).order_by(CollectedItem.collected_at.desc()).first()
    return StatsOut(
        total_sources=db.query(SourceConfig).count(),
        active_sources=db.query(SourceConfig).filter(SourceConfig.is_active == True).count(),
        total_topics=db.query(Topic).count(),
        active_topics=db.query(Topic).filter(Topic.is_active == True).count(),
        total_items=db.query(CollectedItem).count(),
        items_today=db.query(CollectedItem).filter(CollectedItem.collected_at >= today).count(),
        total_tags=db.query(Tag).count(),
        total_schedules=db.query(ScheduleConfig).filter(ScheduleConfig.is_active == True).count(),
        last_collection_at=last.collected_at if last else None,
    )



# ── System Settings ─────────────────────────────────────────────────────

@router.get("/settings", response_model=SystemConfigOut)
def get_settings(db: Session = Depends(get_db)):
    return _get_system_config(db)


@router.put("/settings", response_model=SystemConfigOut)
def update_settings(data: SystemConfigUpdate, db: Session = Depends(get_db)):
    cfg = _get_system_config(db)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(cfg, k, v)
    db.commit()
    db.refresh(cfg)
    return cfg



# ── Config Export / Import ──────────────────────────────────────────────

class ImportConflict(BaseModel):
    id: str
    name: str
    existing: dict | None = None
    incoming: dict
    identical: bool = False


@router.get("/config/export")
def export_config(db: Session = Depends(get_db)):
    sources = [
        {"id": s.id, "name": s.name, "channel": s.channel, "is_active": s.is_active,
         "base_url": s.base_url, "api_endpoint": s.api_endpoint,
         "default_keywords": s.default_keywords, "languages": s.languages}
        for s in db.query(SourceConfig).all()
    ]
    topics_data = []
    for t in db.query(Topic).all():
        td = {"id": t.id, "name": t.name, "description": t.description,
              "keywords": t.keywords, "keyword_tags": t.keyword_tags,
              "description_prompt": t.description_prompt, "source_ids": t.source_ids,
              "collection_model_ids": t.collection_model_ids,
              "ai_research_model_id": t.ai_research_model_id,
              "target_urls": t.target_urls, "auto_tag_rules": t.auto_tag_rules,
              "schedule_cron": t.schedule_cron, "is_scheduled": t.is_scheduled,
              "is_active": t.is_active}
        topics_data.append(td)
    models_data = [
        {"id": m.id, "name": m.name, "provider": m.provider, "base_url": m.base_url,
         "model_name": m.model_name, "temperature": m.temperature,
         "max_tokens": m.max_tokens, "top_p": m.top_p,
         "is_default": m.is_default, "is_active": m.is_active, "description": m.description}
        for m in db.query(ModelConfig).all()
    ]
    tags_data = [
        {"id": tg.id, "namespace": tg.namespace, "value": tg.value,
         "label": tg.label, "color": tg.color}
        for tg in db.query(Tag).all()
    ]
    schedules_data = [
        {"id": s.id, "name": s.name, "cron_expression": s.cron_expression,
         "source_ids": s.source_ids, "topic_ids": s.topic_ids, "is_active": s.is_active}
        for s in db.query(ScheduleConfig).all()
    ]
    tools_data = [
        {"id": st.id, "name": st.name, "tool_type": st.tool_type,
         "is_active": st.is_active, "config_json": st.config_json}
        for st in db.query(SearchToolConfig).all()
    ]

    return {
        "version": "1.0",
        "exported_at": _now().isoformat(),
        "sources": sources, "topics": topics_data,
        "models": models_data, "tags": tags_data,
        "schedules": schedules_data, "search_tools": tools_data,
    }


@router.post("/config/import")
def import_config(data: dict, db: Session = Depends(get_db)):
    imported = {"sources": 0, "topics": 0, "models": 0, "tags": 0, "schedules": 0, "search_tools": 0}
    conflicts = []
    mode = data.get("mode", "skip")

    for item in data.get("sources", []):
        existing = db.query(SourceConfig).filter(SourceConfig.id == item["id"]).first()
        if existing:
            if mode == "skip":
                conflicts.append(ImportConflict(id=item["id"], name=item["name"],
                    existing={"name": existing.name}, incoming=item,
                    identical=existing.name == item.get("name")))
                continue
            elif mode == "overwrite":
                for k, v in item.items():
                    if hasattr(existing, k): setattr(existing, k, v)
        else:
            db.add(SourceConfig(**{k: v for k, v in item.items() if hasattr(SourceConfig, k)}))
        imported["sources"] += 1

    for item in data.get("topics", []):
        existing = db.query(Topic).filter(Topic.id == item["id"]).first()
        if existing:
            if mode == "skip":
                conflicts.append(ImportConflict(id=item["id"], name=item["name"],
                    existing={"name": existing.name}, incoming=item,
                    identical=existing.name == item.get("name")))
                continue
            elif mode == "overwrite":
                for k, v in item.items():
                    if hasattr(existing, k): setattr(existing, k, v)
        else:
            t = Topic(**{k: v for k, v in item.items() if hasattr(Topic, k)})
            db.add(t)
        imported["topics"] += 1

    for item in data.get("models", []):
        existing = db.query(ModelConfig).filter(ModelConfig.id == item["id"]).first()
        if existing:
            if mode == "skip":
                conflicts.append(ImportConflict(id=item["id"], name=item["name"],
                    existing={"name": existing.name}, incoming=item,
                    identical=existing.name == item.get("name")))
                continue
            elif mode == "overwrite":
                for k, v in item.items():
                    if hasattr(existing, k): setattr(existing, k, v)
        else:
            db.add(ModelConfig(**{k: v for k, v in item.items() if hasattr(ModelConfig, k)}))
        imported["models"] += 1

    for item in data.get("tags", []):
        existing = db.query(Tag).filter(Tag.id == item["id"]).first()
        if existing:
            if mode == "skip":
                conflicts.append(ImportConflict(id=item["id"], name=item["value"],
                    existing={"value": existing.value}, incoming=item,
                    identical=existing.value == item.get("value")))
                continue
            elif mode == "overwrite":
                for k, v in item.items():
                    if hasattr(existing, k): setattr(existing, k, v)
        else:
            db.add(Tag(**{k: v for k, v in item.items() if hasattr(Tag, k)}))
        imported["tags"] += 1

    for item in data.get("schedules", []):
        existing = db.query(ScheduleConfig).filter(ScheduleConfig.id == item["id"]).first()
        if existing:
            if mode == "skip":
                conflicts.append(ImportConflict(id=item["id"], name=item["name"],
                    existing={"name": existing.name}, incoming=item,
                    identical=existing.name == item.get("name")))
                continue
            elif mode == "overwrite":
                for k, v in item.items():
                    if hasattr(existing, k): setattr(existing, k, v)
        else:
            db.add(ScheduleConfig(**{k: v for k, v in item.items() if hasattr(ScheduleConfig, k)}))
        imported["schedules"] += 1

    for item in data.get("search_tools", []):
        existing = db.query(SearchToolConfig).filter(SearchToolConfig.id == item["id"]).first()
        if existing:
            if mode == "skip":
                conflicts.append(ImportConflict(id=item["id"], name=item["name"],
                    existing={"name": existing.name}, incoming=item,
                    identical=existing.name == item.get("name")))
                continue
            elif mode == "overwrite":
                for k, v in item.items():
                    if hasattr(existing, k): setattr(existing, k, v)
        else:
            db.add(SearchToolConfig(**{k: v for k, v in item.items() if hasattr(SearchToolConfig, k)}))
        imported["search_tools"] += 1

    db.commit()
    return {"imported": imported, "conflicts": conflicts, "conflict_count": len(conflicts)}
