"""Sources CRUD + validation + connectors listing."""
import hashlib
import json
import logging
from datetime import datetime, timezone
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.collection_schemas import (
    ConnectorInfo, SourceComplianceReview, SourceCreate, SourceOut, SourceUpdate,
)
from app.database import get_db
from app.collection_policy import evaluate_collection_policy
from app.models import SourceConfig
from app.source_taxonomy import SOURCE_GROUP_INPUT_CODES

from ._helpers import CHANNEL_DEFAULTS, _gen_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["sources"])


_CHANNELS_NEEDING_KEY = frozenset({"api_search", "ai_research", "json_api", "commercial"})
_CHANNELS_NO_KEY_NEEDED = frozenset({"web_scrape", "official", "rss", "manual", "social", "deepweb"})
_STALE_CONFIG_ERROR_MARKERS = (
    "api key",
    "apikey",
    "api_key",
    "key",
    "缺少",
    "未配置",
    "暂不能启用",
    "not set",
    "missing",
    "requires",
    "required",
)
_COMPLIANCE_CRITICAL_FIELDS = frozenset({
    "channel", "base_url", "api_endpoint", "homepage_url", "auth_config",
    "crawl_delay_seconds", "rate_limit_rps", "max_items_per_run",
})


def _source_contract_digest(source: SourceConfig) -> str:
    """Hash the approved collection contract without persisting credentials."""
    channel = source.channel.value if hasattr(source.channel, "value") else source.channel
    contract = {
        "channel": str(channel or ""),
        "base_url": source.base_url,
        "api_endpoint": source.api_endpoint,
        "homepage_url": source.homepage_url,
        "auth_config_digest": hashlib.sha256(
            json.dumps(source.auth_config or {}, sort_keys=True, default=str).encode()
        ).hexdigest(),
        "crawl_delay_seconds": source.crawl_delay_seconds,
        "rate_limit_rps": source.rate_limit_rps,
        "max_items_per_run": source.max_items_per_run,
    }
    serialized = json.dumps(contract, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(serialized.encode()).hexdigest()


def _absolute_collection_urls(source: SourceConfig) -> tuple[str, ...]:
    urls: list[str] = []
    for value in (source.base_url, source.api_endpoint):
        if not value:
            continue
        try:
            parsed = urlsplit(str(value))
        except ValueError:
            raise HTTPException(400, "采集地址格式无效") from None
        if parsed.scheme and parsed.hostname:
            urls = [*urls, str(value)]
    return tuple(urls)


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


def _clear_stale_config_error(source: SourceConfig) -> bool:
    """Clear old setup errors once the source has become usable."""
    if not source.is_configured or not source.last_error:
        return False
    error_text = str(source.last_error).casefold()
    if any(marker in error_text for marker in _STALE_CONFIG_ERROR_MARKERS):
        source.last_error = None
        return True
    return False


def _validate_source_group(source_group: str | None) -> None:
    if source_group is not None and source_group not in SOURCE_GROUP_INPUT_CODES:
        # Use 400 because the yz app's legacy numeric 422 handler expects a
        # Pydantic exception object and cannot safely render HTTPException.
        raise HTTPException(400, f"未知的信息源业务分类: {source_group}")


# ── Sources CRUD ────────────────────────────────────────────────────────

@router.get("/sources", response_model=list[SourceOut])
def list_sources(channel: str | None = None, is_active: bool | None = None,
                 configured: bool | None = None, source_group: str | None = None,
                 db: Session = Depends(get_db)):
    q = db.query(SourceConfig)
    if channel:
        q = q.filter(SourceConfig.channel == channel)
    if is_active is not None:
        q = q.filter(SourceConfig.is_active == is_active)
    if configured is not None:
        q = q.filter(SourceConfig.is_configured == configured)
    if source_group:
        _validate_source_group(source_group)
        q = q.filter(SourceConfig.source_group == source_group)
    return q.all()


@router.post("/sources", response_model=SourceOut, status_code=201)
def create_source(data: SourceCreate, db: Session = Depends(get_db)):
    payload = data.model_dump()
    _validate_source_group(payload.get("source_group"))
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
    # New operator-created sources fail closed until an evidence-backed review.
    payload["verification_status"] = "unverified"
    payload["robots_status"] = "unverified"
    payload["terms_status"] = "unverified"
    payload["llm_ingest_allowed"] = False
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
        if _clear_stale_config_error(source):
            updated += 1
    db.commit()
    return {"updated": updated, "configured": sum(1 for source in sources if source.is_configured)}


@router.get("/sources/collection-readiness")
def collection_readiness(db: Session = Depends(get_db)):
    """Explain which sources may fetch, hydrate, and enter LLM curation."""
    sources = db.query(SourceConfig).filter(SourceConfig.is_active == True).all()
    rows = []
    for source in sources:
        decision = evaluate_collection_policy(source)
        rows.append({
            "source_id": source.id,
            "source_name": source.name,
            "automated_fetch_allowed": decision.automated_fetch_allowed,
            "llm_ingest_allowed": decision.llm_ingest_allowed,
            "content_depth": decision.content_depth,
            "reason": decision.reason,
        })
    return {
        "total_active": len(rows),
        "ready_full": sum(row["content_depth"] == "full" for row in rows),
        "excerpt_only": sum(row["content_depth"] == "excerpt" for row in rows),
        "blocked": sum(not row["automated_fetch_allowed"] for row in rows),
        "sources": rows,
    }


@router.post("/sources/reconcile-compliance-profiles")
def reconcile_compliance_profiles(db: Session = Depends(get_db)):
    from app.source_profile_registry import reconcile_verified_source_profiles

    updated_ids = reconcile_verified_source_profiles(db)
    return {"updated": len(updated_ids), "source_ids": updated_ids}


@router.post("/sources/{source_id}/compliance-review", response_model=SourceOut)
def record_compliance_review(
    source_id: str,
    data: SourceComplianceReview,
    db: Session = Depends(get_db),
):
    """Record an explicit, evidence-backed operator decision for a custom source."""
    source = db.query(SourceConfig).filter(SourceConfig.id == source_id).first()
    if source is None:
        raise HTTPException(404, "信息源不存在")
    if not data.confirmed:
        raise HTTPException(400, "必须确认已人工核对 robots、条款和采集地址")
    if data.decision != "block" and (
        data.robots_evidence == "blocked" or data.terms_evidence == "blocked"
    ):
        raise HTTPException(400, "存在阻止证据时不能批准自动采集")
    absolute_urls = _absolute_collection_urls(source)
    if data.decision != "block":
        if not absolute_urls:
            raise HTTPException(400, "批准自动采集前必须配置 HTTPS 采集地址")
        if any(urlsplit(value).scheme.casefold() != "https" for value in absolute_urls):
            raise HTTPException(400, "自动采集审核只批准 HTTPS 地址")

    stamp = datetime.now(timezone.utc)
    source.discovery_urls = [str(url) for url in data.discovery_urls]
    source.legal_basis = data.legal_basis.strip()
    source.compliance_note = data.compliance_note.strip()
    source.verified_at = stamp
    source.compliance_reviewed_by = data.reviewed_by.strip()
    source.compliance_snapshot = {
        "decision": data.decision,
        "reviewed_at": stamp.isoformat(),
        "contract_digest": _source_contract_digest(source),
        "evidence_urls": [str(url) for url in data.discovery_urls],
    }
    if data.decision == "block":
        source.verification_status = "blocked_manual"
        source.robots_status = "blocked_manual_review"
        source.terms_status = "blocked_manual_review"
        source.llm_ingest_allowed = False
    else:
        source.verification_status = f"verified_manual_{stamp.date().isoformat()}"
        source.robots_status = f"{data.robots_evidence}_manual_review"
        source.terms_status = f"{data.terms_evidence}_manual_review"
        source.llm_ingest_allowed = data.decision == "approve_full"
    db.commit()
    db.refresh(source)
    return source


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
    compliance_contract_changed = bool(
        _COMPLIANCE_CRITICAL_FIELDS & update_data.keys()
    )
    if "source_group" in update_data and update_data["source_group"] is None:
        raise HTTPException(400, "信息源业务分类不能为 null")
    _validate_source_group(update_data.get("source_group"))
    for k, v in update_data.items():
        # The form sends null when no advanced JSON is supplied. Preserve an
        # existing connector configuration so a routine API-key edit cannot
        # silently turn a specialised source into the default connector.
        if k == "auth_config" and v is None:
            continue
        if k == "api_key" and not str(v or "").strip():
            continue
        setattr(src, k, v)
    if compliance_contract_changed:
        prior_snapshot = (
            src.compliance_snapshot if isinstance(src.compliance_snapshot, dict) else {}
        )
        src.verification_status = "unverified"
        src.discovery_urls = None
        src.robots_status = "unverified"
        src.terms_status = "unverified"
        src.llm_ingest_allowed = False
        src.origin_resolution_required = True
        src.verified_at = None
        src.compliance_snapshot = {
            **prior_snapshot,
            "invalidated_at": datetime.now(timezone.utc).isoformat(),
            "invalidated_reason": "collection_contract_changed",
        }
    if {"api_key", "channel", "base_url", "api_endpoint", "homepage_url"} & update_data.keys():
        channel_val = src.channel.value if hasattr(src.channel, 'value') else src.channel
        src.is_configured = _eval_configured(
            str(channel_val), getattr(src, 'api_key', None),
            base_url=src.base_url,
            api_endpoint=src.api_endpoint,
            homepage_url=src.homepage_url,
        )
        _clear_stale_config_error(src)
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
            src.is_configured = True
            src.last_error = None
            db.commit()
            db.refresh(src)
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

    policy = evaluate_collection_policy(src)
    return {
        "source_id": source_id,
        "valid": valid,
        "error": error_msg,
        "diagnostics": diagnostics,
        "collection_policy": {
            "automated_fetch_allowed": policy.automated_fetch_allowed,
            "llm_ingest_allowed": policy.llm_ingest_allowed,
            "content_depth": policy.content_depth,
            "reason": policy.reason,
        },
    }


@router.post("/sources/health-check")
async def health_check_sources(
    source_id: str | None = None,
    db: Session = Depends(get_db),
):
    """Batch-check health of all active sources (or a single source)."""
    from app.source_health_check import check_source_health

    summary = await check_source_health(db, source_id=source_id)
    return summary


@router.get("/sources/health-summary")
def health_summary(db: Session = Depends(get_db)):
    """Return health status distribution without triggering a new check."""
    from collections import Counter
    from sqlalchemy import func

    sources = db.query(SourceConfig).filter(SourceConfig.is_active == True).all()
    dist = Counter(s.health_status or "unknown" for s in sources)
    return {
        "total": len(sources),
        "healthy": dist.get("healthy", 0),
        "degraded": dist.get("degraded", 0),
        "failed": dist.get("failed", 0),
        "unreachable": dist.get("unreachable", 0),
        "unknown": dist.get("unknown", 0),
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
