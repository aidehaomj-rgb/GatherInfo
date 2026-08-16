"""Stats, System Settings, Config Export/Import."""
import logging
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.collection_schemas import (
    StatsOut, SystemConfigOut, SystemConfigUpdate,
)
from app.database import get_db
from app.models import (
    CollectedItem, CollectionRun, ModelConfig, PromptTemplate,
    ScheduleConfig, SearchToolConfig, SourceConfig,
    SystemConfig, Tag, Topic,
)
from app.source_taxonomy import SOURCE_GROUP_INPUT_CODES, determine_source_group
from app.time_utils import beijing_day_bounds_utc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["settings"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_import_datetime(value):
    if not isinstance(value, str):
        return value
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _get_system_config(db: Session) -> SystemConfig:
    cfg = db.query(SystemConfig).filter(SystemConfig.id == "global").first()
    if not cfg:
        cfg = SystemConfig(id="global")
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    from app.report_export import normalize_report_output_dir

    normalized_dir = normalize_report_output_dir(cfg.report_output_dir)
    if cfg.report_output_dir != normalized_dir:
        cfg.report_output_dir = normalized_dir
        db.commit()
        db.refresh(cfg)
    return cfg

# ── Stats ───────────────────────────────────────────────────────────────

@router.get("/stats", response_model=StatsOut)
def get_stats(db: Session = Depends(get_db)):
    today, tomorrow = beijing_day_bounds_utc(now=_now())
    last = db.query(CollectedItem).order_by(CollectedItem.collected_at.desc()).first()
    return StatsOut(
        total_sources=db.query(SourceConfig).count(),
        active_sources=db.query(SourceConfig).filter(SourceConfig.is_active == True).count(),
        total_topics=db.query(Topic).count(),
        active_topics=db.query(Topic).filter(Topic.is_active == True).count(),
        total_items=db.query(CollectedItem).count(),
        items_today=db.query(CollectedItem).filter(
            CollectedItem.collected_at >= today,
            CollectedItem.collected_at < tomorrow,
        ).count(),
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
    payload = data.model_dump(exclude_unset=True)
    if "report_output_dir" in payload:
        from app.report_export import normalize_report_output_dir

        payload = {**payload, "report_output_dir": normalize_report_output_dir(payload["report_output_dir"])}
    for k, v in payload.items():
        setattr(cfg, k, v)
    from app.model_defaults import reconcile_default_model
    reconcile_default_model(db)
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


# 可备份/导入的数据分区：key → (模型类, 名称字段)
_IMPORT_SECTIONS = [
    ("sources", SourceConfig, "name"),
    ("topics", Topic, "name"),
    ("prompt_templates", PromptTemplate, "name"),
    ("models", ModelConfig, "name"),
    ("tags", Tag, "value"),
    ("schedules", ScheduleConfig, "name"),
    ("search_tools", SearchToolConfig, "name"),
]

_VALID_IMPORT_MODES = {"append", "overwrite", "skip", "confirm"}


def _prepare_source_item(item: dict) -> dict:
    """导入信息源时剥离凭据与运行时状态，并归一化业务分类。"""
    item = {
        **item,
        "api_key_ref": None,
        "verification_status": "unverified",
        "discovery_urls": None,
        "robots_status": "unverified",
        "terms_status": "unverified",
        "llm_ingest_allowed": False,
        "origin_resolution_required": True,
        "verified_at": None,
    }
    source_group = item.get("source_group") or determine_source_group(item)
    if source_group not in SOURCE_GROUP_INPUT_CODES:
        raise HTTPException(400, f"未知的信息源业务分类: {source_group}")
    item["source_group"] = source_group
    return item


def _prepare_item(section_key: str, item: dict) -> dict:
    if section_key == "sources":
        return _prepare_source_item(item)
    return dict(item)


def _iter_conflicts(db: Session, section_key: str, model_cls, name_field: str, items: list[dict]) -> list[ImportConflict]:
    conflicts: list[ImportConflict] = []
    for item in items:
        existing = db.get(model_cls, item["id"])
        if existing is None:
            continue
        existing_name = getattr(existing, name_field, None)
        incoming_name = item.get(name_field)
        conflicts.append(ImportConflict(
            id=item["id"],
            name=incoming_name or item["id"],
            existing={name_field: existing_name},
            incoming=item,
            identical=existing_name == incoming_name,
        ))
    return conflicts


def _apply_import(db: Session, data: dict, default_mode: str, decisions: dict | None) -> dict:
    imported = {key: 0 for key, _, _ in _IMPORT_SECTIONS}
    conflicts: list[ImportConflict] = []

    for section_key, model_cls, name_field in _IMPORT_SECTIONS:
        for raw in data.get(section_key, []):
            item = _prepare_item(section_key, raw)
            item_id = item["id"]
            existing = db.get(model_cls, item_id)

            if existing is None:
                db.add(model_cls(**{k: v for k, v in item.items() if hasattr(model_cls, k)}))
                imported[section_key] += 1
                continue

            # 冲突：decisions（逐项确认）优先，其次全局 mode
            decision = (decisions or {}).get(item_id) if decisions else default_mode
            if decision == "overwrite":
                for k, v in item.items():
                    if hasattr(existing, k) and k != "id":
                        setattr(existing, k, v)
                imported[section_key] += 1
            elif decision == "append":
                new_id = f"{item_id}-import-{uuid4().hex[:6]}"
                db.add(model_cls(**{
                    **{k: v for k, v in item.items() if hasattr(model_cls, k)},
                    "id": new_id,
                }))
                imported[section_key] += 1
            else:  # skip
                conflicts.append(ImportConflict(
                    id=item_id,
                    name=item.get(name_field) or item_id,
                    existing={name_field: getattr(existing, name_field, None)},
                    incoming=item,
                    identical=getattr(existing, name_field, None) == item.get(name_field),
                ))

    from app.model_defaults import reconcile_default_model
    reconcile_default_model(db)
    db.commit()
    return {"imported": imported, "conflicts": conflicts, "conflict_count": len(conflicts)}


@router.get("/config/export")
def export_config(db: Session = Depends(get_db)):
    sources = [
        {"id": s.id, "name": s.name, "channel": s.channel, "is_active": s.is_active,
         "source_group": s.source_group,
         "base_url": s.base_url, "api_endpoint": s.api_endpoint,
         "default_keywords": s.default_keywords, "languages": s.languages,
         "country_focus": s.country_focus,
         "verification_status": s.verification_status,
         "discovery_urls": s.discovery_urls,
         "robots_status": s.robots_status,
         "terms_status": s.terms_status,
         "llm_ingest_allowed": s.llm_ingest_allowed,
         "origin_resolution_required": s.origin_resolution_required,
         "crawl_delay_seconds": s.crawl_delay_seconds,
         "verified_at": s.verified_at.isoformat() if s.verified_at else None,
         "compliance_note": s.compliance_note}
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
              "is_active": t.is_active,
              "collect_window_days": t.collect_window_days,
              "weekly_digest_enabled": t.weekly_digest_enabled,
              "weekly_digest_model_id": t.weekly_digest_model_id,
              "weekly_digest_target_items": t.weekly_digest_target_items,
              "weekly_digest_part_size": t.weekly_digest_part_size,
              "weekly_digest_min_items": t.weekly_digest_min_items}
        topics_data.append(td)
    prompt_templates_data = [
        {"id": p.id, "name": p.name, "description": p.description,
         "content": p.content, "kind": getattr(p, "kind", "prompt"),
         "is_active": p.is_active}
        for p in db.query(PromptTemplate).all()
    ]
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
         "timezone": s.timezone,
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
        "prompt_templates": prompt_templates_data,
        "models": models_data, "tags": tags_data,
        "schedules": schedules_data, "search_tools": tools_data,
    }


@router.post("/config/import")
def import_config(data: dict, db: Session = Depends(get_db)):
    """导入备份数据。

    mode:
      - ``skip``      直接执行，冲突项跳过并记录
      - ``overwrite`` 直接执行，冲突项覆盖
      - ``append``    直接执行，冲突项以新 id 追加
      - ``confirm``   预检：不写库，返回冲突清单供前端逐项确认
    """
    mode = data.get("mode", "skip")
    if mode not in _VALID_IMPORT_MODES:
        raise HTTPException(400, f"未知的导入模式: {mode}")

    if mode == "confirm":
        conflicts: list[ImportConflict] = []
        for section_key, model_cls, name_field in _IMPORT_SECTIONS:
            items = [_prepare_item(section_key, raw) for raw in data.get(section_key, [])]
            conflicts.extend(_iter_conflicts(db, section_key, model_cls, name_field, items))
        return {"dry_run": True, "conflicts": conflicts, "conflict_count": len(conflicts)}

    return _apply_import(db, data, mode, None)


@router.post("/config/import/apply")
def apply_import_config(data: dict, db: Session = Depends(get_db)):
    """逐项确认后执行导入。body 为完整备份数据 + ``decisions``（{id: append|overwrite|skip}）。"""
    decisions = data.get("decisions") or {}
    return _apply_import(db, data, "skip", decisions)
