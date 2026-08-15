from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import (CollectedItem, ModelConfig, ResearchCase, ResearchCaseEntity,
                        ResearchEntity, ResearchEvidence, ResearchJob, ResearchRound,
                        SearchToolConfig, SourceConfig)
from app.model_defaults import get_default_model
from app.research_agent import create_job, start_job
from app.case_entity_research import build_gap_followups, enrich_case_entities, enrich_entities_with_llm
from app.research_document_reader import read_document
from app.tool_research_agent import run_tool_research
from app.connectors.broad_web_search import (
    BroadWebSearchCollector, ImageSearchCollector, NewsRSSSearchCollector,
    PDFSearchCollector,
)
from types import SimpleNamespace

router = APIRouter(prefix="/api/v1/research", tags=["research"])


class ResearchCreate(BaseModel):
    topic_id: str
    objective: str = Field(min_length=5, max_length=4000)
    model_id: str | None = None
    max_rounds: int = Field(default=3, ge=1, le=6)
    target_items: int = Field(default=10, ge=1, le=100)
    acceptance_policy: dict | None = None


class DocumentRead(BaseModel):
    url: str = Field(min_length=8, max_length=2000)
    render: bool = False
    follow_links: int = Field(default=0, ge=0, le=3)
    actions: list[dict] = Field(default_factory=list, max_length=12)
    find_text: str | None = Field(default=None, max_length=200)


class ToolResearchCreate(BaseModel):
    objective: str = Field(min_length=5, max_length=4000)
    model_id: str | None = None
    max_steps: int = Field(default=6, ge=1, le=10)


class DiscoverySearch(BaseModel):
    queries: list[str] = Field(min_length=1, max_length=20)
    mode: str = Field(default="web", pattern="^(web|news|images|pdf)$")
    max_items: int = Field(default=30, ge=1, le=100)


def _out(job: ResearchJob, db: Session):
    rounds = db.query(ResearchRound).filter(ResearchRound.job_id == job.id).order_by(ResearchRound.round_number).all()
    return {
        "id": job.id, "topic_id": job.topic_id, "objective": job.objective,
        "model_id": job.model_id, "status": job.status, "max_rounds": job.max_rounds,
        "current_round": job.current_round, "target_items": job.target_items,
        "acceptance_policy": job.acceptance_policy or {},
        "acceptance_result": job.acceptance_result or {},
        "run_ids": job.run_ids or [], "result_item_ids": job.result_item_ids or [],
        "result_count": len(job.result_item_ids or []), "progress": job.progress or [],
        "error_log": job.error_log, "created_at": job.created_at,
        "started_at": job.started_at, "completed_at": job.completed_at,
        "rounds": [{"round_number": r.round_number, "status": r.status, "items_new": r.items_new,
                    "run_ids": r.run_ids or [], "error_log": r.error_log} for r in rounds],
    }


@router.post("/jobs", status_code=202)
async def create_research_job(data: ResearchCreate, db: Session = Depends(get_db)):
    try:
        job = create_job(db, **data.model_dump())
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    start_job(job.id)
    return _out(job, db)


@router.get("/jobs")
def list_research_jobs(limit: int = 30, db: Session = Depends(get_db)):
    jobs = db.query(ResearchJob).order_by(ResearchJob.created_at.desc()).limit(min(max(limit, 1), 100)).all()
    return [_out(job, db) for job in jobs]


@router.get("/jobs/{job_id}")
def get_research_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(ResearchJob, job_id)
    if not job:
        raise HTTPException(404, "Research job not found")
    return _out(job, db)


@router.post("/jobs/{job_id}/resume", status_code=202)
def resume_research_job(job_id: str, db: Session = Depends(get_db)):
    job = db.get(ResearchJob, job_id)
    if not job:
        raise HTTPException(404, "Research job not found")
    if job.status == "completed" and not (job.acceptance_result or {}).get("passed"):
        job.max_rounds = min(12, max(job.max_rounds + 2, job.current_round + 2))
        job.status, job.completed_at, job.error_log = "pending", None, None
        db.commit()
    elif job.status == "failed":
        job.status, job.error_log = "pending", None
        db.commit()
    start_job(job.id)
    return _out(job, db)


@router.get("/jobs/{job_id}/items")
def get_research_items(job_id: str, db: Session = Depends(get_db)):
    job = db.get(ResearchJob, job_id)
    if not job:
        raise HTTPException(404, "Research job not found")
    rows = db.query(CollectedItem).filter(CollectedItem.id.in_(job.result_item_ids or [])).all()
    return [{"id": x.id, "title": x.title, "url": x.url, "summary": x.summary,
             "published_at": x.published_at, "quality_score": x.quality_score,
             "relevance_score": x.relevance_score} for x in rows]


@router.post("/items/{item_id}/entities")
def research_item_entities(item_id: str, db: Session = Depends(get_db)):
    item = db.get(CollectedItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    entities = enrich_case_entities(item)
    followups = build_gap_followups([item], window_start="recent", window_end="today")
    db.commit()
    return {"item_id": item.id, "entities": entities, "followup_queries": followups}


@router.post("/documents/read")
async def read_research_document(data: DocumentRead):
    return await read_document(data.url, render=data.render, follow_links=data.follow_links,
                               actions=data.actions, find_text=data.find_text)


@router.post("/items/{item_id}/entities/llm")
async def research_item_entities_llm(item_id: str, model_id: str | None = None, db: Session = Depends(get_db)):
    item = db.get(CollectedItem, item_id)
    if not item:
        raise HTTPException(404, "Item not found")
    model = db.get(ModelConfig, model_id) if model_id else get_default_model(db)
    entities = await enrich_entities_with_llm(item, model)
    db.commit()
    return {"item_id": item.id, "entities": entities}


@router.post("/agent/run")
async def run_research_agent(data: ToolResearchCreate, db: Session = Depends(get_db)):
    model = db.get(ModelConfig, data.model_id) if data.model_id else get_default_model(db)
    if not model:
        raise HTTPException(400, "没有可用的研究模型")
    search_source = next((db.get(SourceConfig, source_id) for source_id in ("tavily", "tavily-search") if db.get(SourceConfig, source_id) and db.get(SourceConfig, source_id).api_key), None)
    if not search_source:
        search_source = db.get(SourceConfig, "ai-smart-web-research")
        if search_source:
            from types import SimpleNamespace
            from app.connectors.ai_research import AIResearchCollector
            key = AIResearchCollector(search_source)._resolve_tavily_api_key()
            search_source = SimpleNamespace(
                id=search_source.id, api_key=key, api_key_ref=None,
                base_url=search_source.base_url, api_endpoint=search_source.api_endpoint,
                auth_config={"search_depth": "advanced", "include_raw_content": True},
                default_keywords=[], default_categories=[], timeout_seconds=45,
                rate_limit_rps=search_source.rate_limit_rps,
            ) if key else None
    return await run_tool_research(data.objective, model, search_config=search_source, max_steps=data.max_steps)


@router.post("/discovery/search")
async def discovery_search(data: DiscoverySearch):
    collector_class = {
        "web": BroadWebSearchCollector,
        "news": NewsRSSSearchCollector,
        "images": ImageSearchCollector,
        "pdf": PDFSearchCollector,
    }[data.mode]
    config = SimpleNamespace(
        id=f"mcp-{data.mode}-discovery", timeout_seconds=45,
        rate_limit_rps=1.0, auth_config={}, api_key=None, api_key_ref=None,
        base_url=None, api_endpoint=None, default_keywords=[],
        default_categories=[],
    )
    response = await collector_class(config).fetch(data.queries, data.max_items)
    return {
        "mode": data.mode,
        "count": len(response.items),
        "errors": response.error_log or [],
        "items": [
            {"title": item.title, "url": item.url, "summary": item.summary,
             "language": item.language, "metadata": item.raw_metadata or {}}
            for item in response.items
        ],
    }


@router.get("/graph/cases")
def list_research_cases(topic_id: str | None = None, limit: int = 100, db: Session = Depends(get_db)):
    query = db.query(ResearchCase)
    if topic_id:
        query = query.filter(ResearchCase.topic_id == topic_id)
    rows = query.order_by(ResearchCase.updated_at.desc()).limit(min(max(limit, 1), 500)).all()
    return [{"id": row.id, "title": row.title, "jurisdiction": row.jurisdiction,
             "china_relevance": row.china_relevance, "verification_status": row.verification_status,
             "source_count": row.source_count, "entity_count": row.entity_count} for row in rows]


@router.get("/tools/catalog")
def list_tool_catalog(db: Session = Depends(get_db)):
    from mcp_server import TOOLS

    categories = {
        "list_topics": "任务管理", "start_research": "任务编排",
        "get_research": "任务管理", "get_research_items": "数据读取",
        "resume_research": "任务编排", "search_items": "数据读取",
        "open_item": "数据读取", "research_entity": "实体研究",
        "read_document": "多模态解析", "extract_document_entities": "实体研究",
        "run_tool_research": "智能研究", "list_research_cases": "案件图谱",
        "open_research_case": "案件图谱", "broad_web_search": "广泛搜索",
        "multilingual_news_search": "多语种搜索", "case_image_search": "多模态搜索",
        "official_pdf_search": "附件搜索",
        "resolve_supply_chain_entity": "供应链核验",
        "search_supply_chain_contracts": "供应链核验",
        "search_supply_chain_trade_records": "供应链核验",
        "deep_search_china_trade_records": "供应链核验",
        "search_supply_chain_part_numbers": "供应链核验",
        "verify_supply_chain_end_use": "供应链核验",
    }
    mcp_tools = [
        {"id": tool["name"], "name": tool["name"], "description": tool["description"],
         "category": categories.get(tool["name"], "其他工具"), "kind": "mcp",
         "is_active": True, "requires_api_key": False,
         "parameter_count": len((tool.get("inputSchema") or {}).get("properties") or {})}
        for tool in TOOLS
    ]
    providers = []
    for row in db.query(SearchToolConfig).order_by(SearchToolConfig.name).all():
        config = row.config_json or {}
        providers.append({
            "id": row.id, "name": row.name, "description": _provider_description(row.tool_type),
            "category": "搜索提供商", "kind": "provider", "tool_type": row.tool_type,
            "is_active": row.is_active, "requires_api_key": bool(config.get("requires_api_key", row.api_key_ref)),
            "config": config,
        })
    return {"mcp_tools": mcp_tools, "providers": providers,
            "summary": {"mcp_count": len(mcp_tools), "provider_count": len(providers),
                        "active_provider_count": sum(1 for item in providers if item["is_active"])}}


def _provider_description(tool_type: str) -> str:
    return {
        "tavily": "深度网页检索与正文发现，适合高相关案例搜索。",
        "broad_web": "无需密钥的广泛网页发现，补充搜索API覆盖盲区。",
        "news_rss": "聚合多语种新闻索引，发现地方媒体和最新公告。",
        "image_search": "查找案件图片及来源页，辅助识别柜号、车牌和运输工具。",
        "pdf_search": "定向发现执法附件、扣押清单、司法文书及PDF公告。",
        "official_enforcement": "直接检索境外海关和执法机关的高可信公开信息。",
        "gdelt": "检索全球多语种新闻事件，扩展国家和地方媒体覆盖。",
        "rss": "按订阅地址持续采集新闻和机构更新。",
    }.get(tool_type, "可配置的互联网信息发现与采集能力。")


@router.get("/graph/cases/{case_id}")
def get_research_case(case_id: str, db: Session = Depends(get_db)):
    case = db.get(ResearchCase, case_id)
    if not case:
        raise HTTPException(404, "Research case not found")
    relations = db.query(ResearchCaseEntity).filter(ResearchCaseEntity.case_id == case_id).all()
    entity_rows = db.query(ResearchEntity).filter(ResearchEntity.id.in_([r.entity_id for r in relations])).all() if relations else []
    evidence = db.query(ResearchEvidence).filter(ResearchEvidence.case_id == case_id).all()
    return {"case": {"id": case.id, "title": case.title, "jurisdiction": case.jurisdiction,
                     "china_relevance": case.china_relevance, "verification_status": case.verification_status},
            "entities": [{"id": row.id, "name": row.canonical_name, "type": row.entity_type,
                          "aliases": row.aliases, "confidence": row.confidence} for row in entity_rows],
            "evidence": [{"id": row.id, "url": row.url, "domain": row.domain,
                          "quote": row.quote, "is_independent": row.is_independent} for row in evidence]}
