"""YMG-Deep integration: bridge selected GatherInfo item sets to YMG-Deep research.

Flow:
  1. User selects an item set (by topic_id + optional batch/run ids, or explicit item_ids).
  2. Backend fetches the items, builds a compact evidence digest.
  3. Calls a locally-available GatherInfo model to produce a <=200 char analysis topic.
  4. Forwards the analysis topic + evidence digest to the YMG-Deep backend
     (POST /api/research) to start a deep research session.
  5. Returns the YMG-Deep session_id + generated analysis topic + evidence summary
     so the frontend can surface the handoff and open YMG-Deep.

YMG-Deep project lives at /Users/m4max/Documents/YMG-Deep and exposes:
  POST /api/research { topic, requirements, model_id?, depth?, mode? } -> { session_id }
"""
import logging
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm_client import call_llm
from app.models import CollectedItem, ModelConfig, Topic

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/ymg-deep", tags=["ymg-deep"])

# YMG-Deep backend default endpoint (local dev).
YMG_DEEP_BASE_URL = "http://127.0.0.1:8000"
YMG_DEEP_TIMEOUT = 30


# ── Schemas ─────────────────────────────────────────────────────────────


class YmgAnalyzeRequest(BaseModel):
    """Request to bridge a GatherInfo item set into a YMG-Deep research session."""
    topic_id: str | None = Field(default=None, description="主题ID（用于取条目）")
    item_ids: list[str] | None = Field(default=None, description="显式条目ID列表（优先于 topic_id）")
    collection_run_ids: list[str] | None = Field(default=None, description="限定采集批次")
    model_id: str | None = Field(default=None, description="用于生成分析主题的 GatherInfo 模型ID")
    ymg_depth: str = Field(default="standard", description="YMG-Deep 深度: standard|deep")
    ymg_mode: str = Field(default="swarm", description="YMG-Deep 模式: swarm|solo")
    extra_requirements: str | None = Field(default=None, description="附加要求")


class YmgEvidenceItem(BaseModel):
    id: str
    title: str
    url: str | None = None
    summary: str | None = None
    source: str | None = None
    published_at: str | None = None
    language: str | None = None


class YmgAnalyzeResponse(BaseModel):
    analysis_topic: str
    evidence_count: int
    evidence_digest: str
    evidence_items: list[YmgEvidenceItem] = []
    ymg_session_id: str | None = None
    ymg_status: str = "pending"
    ymg_message: str | None = None
    ymg_base_url: str = YMG_DEEP_BASE_URL


class YmgHealthResponse(BaseModel):
    reachable: bool
    base_url: str
    message: str | None = None


# ── Helpers ─────────────────────────────────────────────────────────────


def _resolve_items(
    db: Session,
    topic_id: str | None,
    item_ids: list[str] | None,
    collection_run_ids: list[str] | None,
    limit: int = 80,
) -> list[CollectedItem]:
    """Fetch the item set selected by the user."""
    if item_ids:
        rows = (
            db.query(CollectedItem)
            .filter(CollectedItem.id.in_(item_ids[:limit]))
            .order_by(CollectedItem.published_at.desc())
            .all()
        )
        return rows
    if not topic_id:
        raise HTTPException(400, "需提供 topic_id 或 item_ids")
    q = db.query(CollectedItem).filter(CollectedItem.topic_id == topic_id)
    if collection_run_ids:
        q = q.filter(CollectedItem.run_id.in_(collection_run_ids))
    return q.order_by(CollectedItem.published_at.desc()).limit(limit).all()


def _build_evidence_digest(items: list[CollectedItem]) -> tuple[str, list[YmgEvidenceItem]]:
    """Build a compact digest of the evidence set + structured item list."""
    evidence_items: list[YmgEvidenceItem] = []
    lines: list[str] = [f"本地知识库信息集（共 {len(items)} 条）:", ""]
    for idx, it in enumerate(items[:80], 1):
        title = it.title_zh or it.title or "无标题"
        summary = (it.summary_zh or it.summary or (it.content or "")[:200]).strip()
        evidence_items.append(YmgEvidenceItem(
            id=it.id, title=title[:200], url=it.url,
            summary=summary[:300] or None,
            source=it.source_id, published_at=it.published_at.isoformat() if it.published_at else None,
            language=it.language,
        ))
        url_line = f"\n    链接: {it.url}" if it.url else ""
        lines.append(
            f"[{idx}] {title}"
            f"{f' | 来源: {it.source_id}' if it.source_id else ''}"
            f"{f' | 时间: {it.published_at:%Y-%m-%d}' if it.published_at else ''}"
            f"\n    摘要: {summary[:180]}"
            f"{url_line}"
        )
    return "\n".join(lines), evidence_items


def _pick_model(db: Session, model_id: str | None) -> ModelConfig:
    """Resolve a usable GatherInfo model for analysis-topic generation."""
    if model_id:
        m = db.query(ModelConfig).filter(ModelConfig.id == model_id).first()
        if m and m.is_active:
            return m
    default = (
        db.query(ModelConfig)
        .filter(ModelConfig.is_active == True, ModelConfig.is_default == True)
        .first()
    )
    if default:
        return default
    any_active = db.query(ModelConfig).filter(ModelConfig.is_active == True).first()
    if any_active:
        return any_active
    raise HTTPException(400, "没有可用的 GatherInfo 模型来生成分析主题，请先在模型配置中启用一个模型。")


def _build_topic_prompt(items: list[CollectedItem], topic: Topic | None) -> str:
    """Prompt the local model to generate a <=200 char analysis topic."""
    titles = "\n".join(f"- {(it.title_zh or it.title or '').strip()}" for it in items[:30])
    topic_name = topic.name if topic else "（未指定主题）"
    topic_kw = ""
    if topic and topic.keywords:
        topic_kw = f"\n主题关键词: {', '.join(topic.keywords)}"
    return (
        "你是一位跨境贸易与监管情报分析师。基于以下本地已采集的信息集合，"
        "生成一个用于深度研究的分析主题。要求：\n"
        "1. 一小段话，不超过 200 字\n"
        "2. 概括信息集合的核心议题与研究方向\n"
        "3. 语言：中文\n"
        "4. 只输出主题文本，不要加前缀、编号或解释\n\n"
        f"所属主题: {topic_name}{topic_kw}\n"
        f"信息条目标题（共 {len(items)} 条，展示前 30 条）:\n{titles}"
    )


async def _forward_to_ymg(
    analysis_topic: str,
    evidence_digest: str,
    extra_requirements: str | None,
    depth: str,
    mode: str,
) -> dict[str, Any]:
    """Start a YMG-Deep research session with the analysis topic + evidence."""
    requirements_parts = [
        "以下信息来自 GatherInfo 本地知识库，请在分析中参考运用：",
        "",
        evidence_digest[:6000],
    ]
    if extra_requirements:
        requirements_parts.append("")
        requirements_parts.append(f"附加要求: {extra_requirements}")

    payload = {
        "topic": analysis_topic,
        "requirements": "\n".join(requirements_parts),
        "depth": depth,
        "mode": mode,
    }
    try:
        async with httpx.AsyncClient(timeout=YMG_DEEP_TIMEOUT) as client:
            resp = await client.post(f"{YMG_DEEP_BASE_URL}/api/research", json=payload)
            if resp.status_code != 200:
                return {
                    "session_id": None,
                    "status": "failed",
                    "message": f"YMG-Deep 返回 {resp.status_code}: {resp.text[:300]}",
                }
            data = resp.json()
            return {
                "session_id": data.get("session_id"),
                "status": "started",
                "message": None,
            }
    except httpx.ConnectError:
        return {
            "session_id": None,
            "status": "unreachable",
            "message": f"无法连接 YMG-Deep 后端 ({YMG_DEEP_BASE_URL})，请确认 YMG-Deep 服务已启动。",
        }
    except Exception as exc:
        return {
            "session_id": None,
            "status": "failed",
            "message": f"转发到 YMG-Deep 失败: {exc}",
        }


# ── Routes ──────────────────────────────────────────────────────────────


@router.get("/health", response_model=YmgHealthResponse)
async def ymg_health():
    """Check whether the YMG-Deep backend is reachable."""
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{YMG_DEEP_BASE_URL}/api/health")
            ok = resp.status_code == 200
            return YmgHealthResponse(
                reachable=ok,
                base_url=YMG_DEEP_BASE_URL,
                message="YMG-Deep 服务在线" if ok else f"状态码 {resp.status_code}",
            )
    except Exception as exc:
        return YmgHealthResponse(
            reachable=False,
            base_url=YMG_DEEP_BASE_URL,
            message=f"YMG-Deep 未启动: {exc}",
        )


@router.post("/analyze", response_model=YmgAnalyzeResponse)
async def ymg_analyze(data: YmgAnalyzeRequest, db: Session = Depends(get_db)):
    """Bridge a selected GatherInfo item set into a YMG-Deep deep-research session.

    Steps: resolve items -> build evidence digest -> local model generates
    a <=200 char analysis topic -> forward to YMG-Deep /api/research.
    """
    items = _resolve_items(db, data.topic_id, data.item_ids, data.collection_run_ids)
    if not items:
        raise HTTPException(400, "所选信息集没有采集条目，请先采集或在条目页选择。")

    topic = db.query(Topic).filter(Topic.id == data.topic_id).first() if data.topic_id else None
    evidence_digest, evidence_items = _build_evidence_digest(items)

    model = _pick_model(db, data.model_id)
    prompt = _build_topic_prompt(items, topic)
    try:
        result = await call_llm(model, prompt)
        analysis_topic = (result.get("content") or "").strip()
        if not analysis_topic:
            raise ValueError("模型返回空内容")
        analysis_topic = analysis_topic[:500]
    except Exception as exc:
        logger.warning("analysis topic generation failed: %s", exc)
        # Fallback: synthesize a topic from the first few item titles.
        head = "; ".join((it.title_zh or it.title or "").strip() for it in items[:5] if it.title)
        analysis_topic = f"基于本地知识库信息集的深度分析：{head}"[:200]

    forward = await _forward_to_ymg(
        analysis_topic, evidence_digest, data.extra_requirements,
        data.ymg_depth, data.ymg_mode,
    )

    return YmgAnalyzeResponse(
        analysis_topic=analysis_topic,
        evidence_count=len(items),
        evidence_digest=evidence_digest,
        evidence_items=evidence_items[:20],
        ymg_session_id=forward.get("session_id"),
        ymg_status=forward.get("status", "pending"),
        ymg_message=forward.get("message"),
        ymg_base_url=YMG_DEEP_BASE_URL,
    )
