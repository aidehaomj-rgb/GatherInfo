"""Sources CRUD + validation + connectors listing."""
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.collection_schemas import (
    ConnectorInfo, SourceCreate, SourceOut, SourceUpdate,
)
from app.database import get_db
from app.models import SourceConfig

from ._helpers import CHANNEL_DEFAULTS, _gen_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["sources"])


_CHANNELS_NEEDING_KEY = frozenset({"api_search", "ai_research", "json_api", "commercial"})
_CHANNELS_NO_KEY_NEEDED = frozenset({"web_scrape", "official", "rss", "manual", "social", "deepweb"})


def _eval_configured(
    channel: str,
    api_key: str | None,
    *,
    base_url: str | None = None,
    api_endpoint: str | None = None,
    homepage_url: str | None = None,
) -> bool:
    """Determine whether a source has the minimum viable collection setup."""
    channel = str(channel or "").lower()
    has_address = bool((base_url or api_endpoint or homepage_url or "").strip())
    if channel == "manual":
        return True
    if channel in _CHANNELS_NO_KEY_NEEDED:
        return has_address
    return bool(api_key)


# ── Sources CRUD ────────────────────────────────────────────────────────

@router.get("/sources", response_model=list[SourceOut])
def list_sources(channel: str | None = None, is_active: bool | None = None,
                 configured: bool | None = None, db: Session = Depends(get_db)):
    q = db.query(SourceConfig)
    if channel:
        q = q.filter(SourceConfig.channel == channel)
    if is_active is not None:
        q = q.filter(SourceConfig.is_active == is_active)
    if configured is not None:
        q = q.filter(SourceConfig.is_configured == configured)
    return q.all()


@router.post("/sources", response_model=SourceOut, status_code=201)
def create_source(data: SourceCreate, db: Session = Depends(get_db)):
    payload = data.model_dump()
    src_id = payload.get("id")
    if not src_id:
        src_id = _gen_id(
            data.name,
            exists_fn=lambda c: db.query(SourceConfig).filter(
                SourceConfig.id == c).first() is not None,
        )
    elif db.query(SourceConfig).filter(SourceConfig.id == src_id).first():
        raise HTTPException(400, f"信息源 '{src_id}' 已存在")
    payload["id"] = src_id
    payload["is_configured"] = _eval_configured(
        payload.get("channel", ""), payload.get("api_key"),
        base_url=payload.get("base_url"),
        api_endpoint=payload.get("api_endpoint"),
        homepage_url=payload.get("homepage_url"),
    )
    try:
        src = SourceConfig(**payload)
        db.add(src)
        db.commit()
        db.refresh(src)
    except Exception as exc:
        db.rollback()
        logger.error("create_source failed: %s", exc)
        raise HTTPException(500, f"创建信息源失败: {exc}")
    return src


@router.post("/sources/reconcile-readiness")
def reconcile_source_readiness(db: Session = Depends(get_db)):
    """Promote public website sources that already have a usable address."""
    sources = db.query(SourceConfig).all()
    updated = 0
    for source in sources:
        channel = source.channel.value if hasattr(source.channel, "value") else str(source.channel)
        configured = _eval_configured(
            channel, source.api_key, base_url=source.base_url,
            api_endpoint=source.api_endpoint, homepage_url=source.homepage_url,
        )
        if source.is_configured != configured:
            source.is_configured = configured
            updated += 1
    db.commit()
    return {"updated": updated, "configured": sum(1 for source in sources if source.is_configured)}


@router.get("/sources/{source_id}", response_model=SourceOut)
def get_source(source_id: str, db: Session = Depends(get_db)):
    src = db.query(SourceConfig).filter(SourceConfig.id == source_id).first()
    if not src:
        raise HTTPException(404)
    return src


@router.put("/sources/{source_id}", response_model=SourceOut)
def update_source(source_id: str, data: SourceUpdate, db: Session = Depends(get_db)):
    src = db.query(SourceConfig).filter(SourceConfig.id == source_id).first()
    if not src:
        raise HTTPException(404)
    update_data = data.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        # The form sends null when no advanced JSON is supplied. Preserve an
        # existing connector configuration so a routine API-key edit cannot
        # silently turn a specialised source into the default connector.
        if k == "auth_config" and v is None:
            continue
        setattr(src, k, v)
    if {"api_key", "channel", "base_url", "api_endpoint", "homepage_url"} & update_data.keys():
        channel_val = src.channel.value if hasattr(src.channel, 'value') else src.channel
        src.is_configured = _eval_configured(
            str(channel_val), getattr(src, 'api_key', None),
            base_url=src.base_url,
            api_endpoint=src.api_endpoint,
            homepage_url=src.homepage_url,
        )
    db.commit()
    db.refresh(src)
    return src


@router.delete("/sources/{source_id}")
def delete_source(source_id: str, db: Session = Depends(get_db)):
    src = db.query(SourceConfig).filter(SourceConfig.id == source_id).first()
    if not src:
        raise HTTPException(404)
    db.delete(src)
    db.commit()
    return {"ok": True}


@router.post("/sources/{source_id}/validate")
async def validate_source(source_id: str, db: Session = Depends(get_db)):
    """Enhanced validation: returns detailed diagnostics about the source configuration."""
    src = db.query(SourceConfig).filter(SourceConfig.id == source_id).first()
    if not src:
        raise HTTPException(404)

    diagnostics: list[str] = []
    valid = False
    error_msg: str | None = None

    from app.connectors.base import ConnectorRegistry

    # Check channel registration
    try:
        connector = ConnectorRegistry.create(src)
    except ValueError as exc:
        return {
            "source_id": source_id, "valid": False,
            "error": f"Connector not found for channel '{src.channel}': {exc}",
            "diagnostics": [f"渠道 '{src.channel}' 没有注册连接器"],
        }

    # Check API key for channels that need one
    channel_str = str(src.channel.value if hasattr(src.channel, 'value') else src.channel)
    if channel_str in _CHANNELS_NEEDING_KEY and not src.api_key:
        diagnostics.append(f"该渠道 ({channel_str}) 需要 API Key，当前未配置。"
                           f"请在编辑表单中填入 API Key 或设置对应环境变量。")
    elif channel_str in _CHANNELS_NO_KEY_NEEDED:
        diagnostics.append(f"该渠道 ({channel_str}) 无需 API Key，可直接使用。")
    elif src.api_key:
        diagnostics.append("API Key 已配置。")

    # Check base_url
    if not src.base_url:
        if channel_str not in ("rss", "manual"):
            diagnostics.append("base_url 未配置，可能无法正常采集。")
    else:
        diagnostics.append(f"base_url: {src.base_url}")

    # Attempt actual connectivity check
    try:
        valid = await connector.validate()
        if valid:
            diagnostics.append("连接测试通过 ✓")
        else:
            diagnostics.append("连接测试失败：无法连接或认证失败。")
    except Exception as exc:
        error_msg = str(exc)
        diagnostics.append(f"连接测试异常: {error_msg}")

    # Collect all missing fields
    if channel_str in _CHANNELS_NEEDING_KEY and not src.api_key:
        channel_hints = {
            "api_search": "Search API requires an API Key.",
            "ai_research": "AI research requires a Tavily API Key; Baidu is optional in auth_config.",
            "json_api": "JSON API requires its provider API Key and endpoint.",
            "commercial": "Commercial API requires a purchased API Key.",
        }
        diagnostics.append(channel_hints.get(channel_str, "请配置 API Key。"))

    return {
        "source_id": source_id,
        "valid": valid,
        "error": error_msg,
        "diagnostics": diagnostics,
    }


# ── Connectors ──────────────────────────────────────────────────────────

@router.get("/connectors", response_model=list[ConnectorInfo])
def list_connectors():
    from app.connectors.base import ConnectorRegistry
    out = []
    for ch in ConnectorRegistry.available_channels():
        meta = CHANNEL_DEFAULTS.get(ch, {})
        out.append(ConnectorInfo(
            channel=ch,
            description=meta.get("description", ""),
            default_base_url=meta.get("default_base_url") or None,
            default_api_endpoint=meta.get("default_api_endpoint") or None,
            required_fields=meta.get("required_fields", []),
            optional_fields=meta.get("optional_fields", []),
            homepage_hint=meta.get("homepage_hint") or None,
        ))
    return out
