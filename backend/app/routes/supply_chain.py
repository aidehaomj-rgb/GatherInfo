"""US defence supply-chain penetration analysis routes."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.connectors.tavily_search import TavilyCollector
from app.database import get_db
from app.llm_client import call_llm
from app.model_defaults import get_default_model
from app.prompt_seed import resolve_supply_chain_expert_prompt
from app.supply_chain_online import discover_online_supply_chains
from app.models import (
    ModelConfig,
    SourceConfig,
    SupplyChainCase,
    SupplyChainDiscoveryCandidate,
    SupplyChainEntity,
    SupplyChainEvidence,
    SupplyChainInvestigation,
    SupplyChainOpenSourceEvidence,
    SupplyChainReport,
    SupplyChainShipment,
)

router = APIRouter(prefix="/api/v1/supply-chain", tags=["supply-chain"])

SUPPLY_CHAIN_MCP_TOOLS = [
    "resolve_supply_chain_entity",
    "search_supply_chain_contracts",
    "search_supply_chain_trade_records",
    "deep_search_china_trade_records",
    "search_supply_chain_part_numbers",
    "verify_supply_chain_end_use",
]


def _now():
    return datetime.now(timezone.utc)


def _configured_supply_chain_search_sources(db: Session) -> list[SourceConfig]:
    sources: list[SourceConfig] = []
    provider_types: set[str] = set()
    for source_id in ("baidu-search", "tavily", "tavily-search"):
        source = db.get(SourceConfig, source_id)
        if not source or not source.is_active:
            continue
        collector = TavilyCollector(source)
        provider_type = str(collector.search_type or source_id)
        if not collector.api_key or provider_type in provider_types:
            continue
        sources = [*sources, source]
        provider_types = {*provider_types, provider_type}
    return sources


def _parse_date(value: str | None):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc)


def _parse_online_date(value: str | None):
    """Ignore an unparseable model date instead of failing the whole discovery run."""
    try:
        return _parse_date(value)
    except (TypeError, ValueError):
        return None


def _norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (value or "").casefold())


def _identity_matches(left: str | None, right: str | None) -> bool:
    """Match legal names/products across bilingual and punctuation variants."""
    a, b = _norm(left), _norm(right)
    if not a or not b:
        return False
    return a == b or (min(len(a), len(b)) >= 5 and (a in b or b in a))


def _chain_signature_matches(
    importer: str | None,
    product: str | None,
    existing_importer: str | None,
    existing_product: str | None,
) -> bool:
    return _identity_matches(importer, existing_importer) and _identity_matches(product, existing_product)


def _dump(row, fields: list[str]) -> dict:
    return {field: getattr(row, field) for field in fields}


ENTITY_FIELDS = [
    "id", "name", "name_zh", "country", "entity_type", "aliases", "parent_id",
    "defense_roles", "source_url", "notes", "created_at", "updated_at",
]
CASE_FIELDS = [
    "id", "country", "title", "procurement_agency", "procurement_reference",
    "procurement_date", "supplier_entity_id", "product", "target_program",
    "contract_value", "currency", "source_url", "source_excerpt", "status",
    "created_at", "updated_at",
]
SHIPMENT_FIELDS = [
    "id", "exporter_name", "exporter_country", "importer_entity_id", "importer_name",
    "product", "hs_code", "shipment_date", "weight_kg", "quantity", "quantity_unit",
    "origin_country", "destination_country", "bill_no", "source_name", "source_url",
    "raw_record", "created_at",
]
EVIDENCE_FIELDS = [
    "id", "case_id", "shipment_id", "relation_type", "evidence_grade", "score",
    "status", "reasoning", "verified_facts", "model_review", "is_reportable",
    "created_at", "updated_at",
]
OPEN_SOURCE_EVIDENCE_FIELDS = [
    "id", "case_id", "title", "source_type", "source_publisher", "source_url",
    "source_excerpt", "verified_facts", "evidence_grade", "status", "limitations",
    "created_at", "updated_at",
]
REPORT_FIELDS = [
    "id", "country", "title", "case_ids", "evidence_ids", "model_id", "status",
    "content", "summary", "error_log", "generated_at", "created_at",
]
CANDIDATE_FIELDS = [
    "id", "country", "case_id", "shipment_id", "supplier_entity_id", "title",
    "target_program", "exporter_name", "importer_name", "product", "score",
    "evidence_grade", "verified_facts", "status", "review_note",
    "investigation_id", "created_at", "reviewed_at",
]
INVESTIGATION_FIELDS = [
    "id", "country", "name", "description", "status", "entity_ids", "case_ids",
    "shipment_ids", "evidence_ids", "open_source_evidence_ids", "report_ids",
    "created_at", "updated_at",
]

COUNTRY_NAMES = {
    "United States": "美国",
    "India": "印度",
    "Japan": "日本",
    "Taiwan": "中国台湾",
}


class InvestigationInput(BaseModel):
    name: str
    country: str = "United States"
    description: str | None = None


def _ensure_default_investigation(db: Session) -> None:
    if db.get(SupplyChainInvestigation, "inv-us-ultralife-battery"):
        return
    case_ids = [
        row[0] for row in db.query(SupplyChainCase.id).filter(
            SupplyChainCase.id.in_([
                "case-ultralife-mk68",
                "case-ultralife-ba5390-dla",
                "case-ultralife-cwb",
            ])
        ).all()
    ]
    shipment_ids = [
        row[0] for row in db.query(SupplyChainShipment.id).filter(
            SupplyChainShipment.id.in_([
                "shp-able-ultralife-202603-06",
                "shp-goldencell-ultralife-202606-07",
                "shp-lishen-ultralife-202603-05",
            ])
        ).all()
    ]
    evidence_ids = [
        row[0] for row in db.query(SupplyChainEvidence.id).filter(
            SupplyChainEvidence.case_id.in_(case_ids)
        ).all()
    ] if case_ids else []
    open_source_ids = [
        row[0] for row in db.query(SupplyChainOpenSourceEvidence.id).filter(
            SupplyChainOpenSourceEvidence.case_id.in_(case_ids)
        ).all()
    ] if case_ids else []
    report_ids = [
        row[0] for row in db.query(SupplyChainReport.id).filter(
            SupplyChainReport.country == "United States"
        ).all()
    ]
    entity_ids = {
        row[0] for row in db.query(SupplyChainCase.supplier_entity_id).filter(
            SupplyChainCase.id.in_(case_ids),
            SupplyChainCase.supplier_entity_id.isnot(None),
        ).all()
    } if case_ids else set()
    entity_ids.update(
        row[0] for row in db.query(SupplyChainShipment.importer_entity_id).filter(
            SupplyChainShipment.id.in_(shipment_ids),
            SupplyChainShipment.importer_entity_id.isnot(None),
        ).all()
    )
    db.add(SupplyChainInvestigation(
        id="inv-us-ultralife-battery",
        country="United States",
        name="美军电池供应链",
        description="Ultralife军用电池采购与中国锂电池供应商贸易链条",
        entity_ids=sorted(entity_ids),
        case_ids=case_ids,
        shipment_ids=shipment_ids,
        evidence_ids=evidence_ids,
        open_source_evidence_ids=open_source_ids,
        report_ids=report_ids,
    ))
    db.commit()


def _get_investigation(
    db: Session, country: str, investigation_id: str | None
) -> SupplyChainInvestigation | None:
    if not investigation_id:
        return None
    row = db.get(SupplyChainInvestigation, investigation_id)
    if not row or row.country != country:
        raise HTTPException(404, "供应链项目不存在或不属于当前国家方向")
    return row


def _attach(db: Session, investigation_id: str | None, field: str, value: str) -> None:
    if not investigation_id:
        return
    row = db.get(SupplyChainInvestigation, investigation_id)
    if not row:
        raise HTTPException(404, "供应链项目不存在")
    values = list(getattr(row, field) or [])
    if value not in values:
        values.append(value)
        setattr(row, field, values)
        row.updated_at = _now()


def _dump_investigation(row: SupplyChainInvestigation, db: Session) -> dict:
    data = _dump(row, INVESTIGATION_FIELDS)
    entities = (
        db.query(SupplyChainEntity)
        .filter(SupplyChainEntity.id.in_(row.entity_ids or []))
        .all()
        if row.entity_ids else []
    )
    cases = (
        db.query(SupplyChainCase)
        .filter(SupplyChainCase.id.in_(row.case_ids or []))
        .all()
        if row.case_ids else []
    )
    shipments = (
        db.query(SupplyChainShipment)
        .filter(SupplyChainShipment.id.in_(row.shipment_ids or []))
        .all()
        if row.shipment_ids else []
    )
    linked_evidence = (
        db.query(SupplyChainEvidence)
        .filter(SupplyChainEvidence.id.in_(row.evidence_ids or []))
        .all()
        if row.evidence_ids else []
    )
    open_evidence = (
        db.query(SupplyChainOpenSourceEvidence)
        .filter(SupplyChainOpenSourceEvidence.id.in_(row.open_source_evidence_ids or []))
        .all()
        if row.open_source_evidence_ids else []
    )
    reports = (
        db.query(SupplyChainReport)
        .filter(SupplyChainReport.id.in_(row.report_ids or []))
        .all()
        if row.report_ids else []
    )

    gaps: list[str] = []
    anonymous_markers = ("undisclosed", "anonymous", "unknown", "待识别", "未披露", "匿名", "候选")
    unresolved_entities = [
        item for item in entities
        if any(marker in f"{item.name} {item.name_zh or ''} {item.entity_type}".casefold()
               for marker in anonymous_markers)
    ]
    entity_score = (14 if unresolved_entities else 15) if entities else 0
    if not entities:
        gaps.append("尚未识别供应链主体")
    elif unresolved_entities:
        gaps.append(f"仍有{len(unresolved_entities)}个匿名、待识别或候选主体")

    generic_refs = {"", "公开源供应链调查", "待补充", "公告编号待补充"}
    specific_cases = [
        item for item in cases
        if (item.procurement_reference or "").strip() not in generic_refs
        and item.procurement_date and item.source_url
    ]
    case_score = (15 if len(specific_cases) == len(cases) else 14) if cases else 0
    if not cases:
        gaps.append("尚未录入军方采购或合作项目")
    elif len(specific_cases) < len(cases):
        gaps.append(f"有{len(cases) - len(specific_cases)}个项目缺少具体合同编号、日期或原始公告")

    def shipment_quality(item: SupplyChainShipment) -> float:
        checks = [
            item.shipment_date, item.exporter_name, item.importer_name, item.product,
            item.source_url, item.bill_no or item.raw_record,
        ]
        return sum(bool(value) for value in checks) / len(checks)

    shipment_ratio = (
        sum(shipment_quality(item) for item in shipments) / len(shipments)
        if shipments else 0
    )
    shipment_score = (25 if shipment_ratio == 1 else 24) if shipments else 0
    if not shipments:
        gaps.append("尚无可核验的批次级跨境贸易记录")
    elif shipment_score < 25:
        gaps.append("部分贸易记录缺少日期、提单号或原始数据链接")

    grade_weights = {"A": 1.0, "B": 0.72, "C": 0.42, "D": 0.2}
    evidence_values: list[float] = []
    limited_count = 0
    for item in open_evidence:
        value = grade_weights.get((item.evidence_grade or "").upper(), 0.2)
        if item.status != "verified":
            value *= 0.65
        if item.limitations:
            value *= 0.82
            limited_count += 1
        evidence_values.append(value)
    for item in linked_evidence:
        value = min(max((item.score or 0) / 100, 0), 1)
        if not item.is_reportable:
            value *= 0.65
        if item.status not in {"verified", "completed"}:
            value *= 0.75
        evidence_values.append(value)
    weak_count = sum(
        1 for item in open_evidence
        if (item.evidence_grade or "").upper() not in {"A"} or item.status != "verified"
    )
    all_evidence_strong = bool(evidence_values) and not limited_count and not weak_count and all(
        item.is_reportable and item.status in {"verified", "completed"}
        for item in linked_evidence
    )
    evidence_score = (30 if all_evidence_strong else 28) if evidence_values else 0
    if not evidence_values:
        gaps.append("尚未形成可核验的证据材料")
    if limited_count:
        gaps.append(f"有{limited_count}项证据明确标注适用边界或待核实事项")
    if weak_count:
        gaps.append(f"有{weak_count}项公开源证据未达到A级已核验标准")

    end_use_entities = {
        "military_end_user", "government_end_user", "government_agency"
    }
    has_end_user = any(item.entity_type in end_use_entities for item in entities)
    has_target_program = any(
        item.target_program and "待" not in item.target_program for item in cases
    )
    end_use_score = 10 if has_end_user and has_target_program else 8 if has_target_program else 0
    if not has_end_user:
        gaps.append("最终用户尚未作为独立主体核实")
    if not has_target_program:
        gaps.append("最终装备或应用项目尚未核实")

    completed_reports = [
        item for item in reports
        if item.status == "completed" and item.content and item.summary
    ]
    report_score = 5 if completed_reports else 0
    if not completed_reports:
        gaps.append("尚无基于现有证据完成的分析报告")

    components = {
        "主体实名": entity_score,
        "采购合同": case_score,
        "贸易记录": shipment_score,
        "证据质量": evidence_score,
        "最终用途": end_use_score,
        "分析报告": report_score,
    }
    maximums = {
        "主体实名": 15,
        "采购合同": 15,
        "贸易记录": 25,
        "证据质量": 30,
        "最终用途": 10,
        "分析报告": 5,
    }
    score = sum(components.values())
    if not shipments:
        score = min(score, 70)
    data["completeness_score"] = score
    data["completeness_level"] = (
        "证据闭合" if score >= 99 and not gaps
        else "较高可信" if score >= 95
        else "部分核实" if score >= 90
        else "初步核实" if score >= 70
        else "初步成链" if score >= 40 else "线索阶段"
    )
    data["completeness_details"] = components
    data["completeness_maximums"] = maximums
    data["verification_gaps"] = gaps
    return data


@router.get("/investigations")
def list_investigations(country: str = "United States", db: Session = Depends(get_db)):
    _ensure_default_investigation(db)
    rows = db.query(SupplyChainInvestigation).filter(
        SupplyChainInvestigation.country == country
    ).order_by(SupplyChainInvestigation.created_at.asc()).all()
    return [_dump_investigation(row, db) for row in rows]


@router.post("/investigations")
def create_investigation(data: InvestigationInput, db: Session = Depends(get_db)):
    if data.country not in COUNTRY_NAMES:
        raise HTTPException(400, "当前仅支持美国、印度、日本和中国台湾方向")
    row = SupplyChainInvestigation(
        id=f"inv-{uuid4().hex[:12]}",
        **data.model_dump(),
        entity_ids=[], case_ids=[], shipment_ids=[], evidence_ids=[],
        open_source_evidence_ids=[], report_ids=[],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return _dump_investigation(row, db)


class EntityInput(BaseModel):
    name: str
    name_zh: str | None = None
    country: str = "United States"
    entity_type: str = "defense_supplier"
    aliases: list[str] = Field(default_factory=list)
    parent_id: str | None = None
    defense_roles: list[str] = Field(default_factory=list)
    source_url: str | None = None
    notes: str | None = None
    investigation_id: str | None = None


class CaseInput(BaseModel):
    title: str
    country: str = "United States"
    procurement_agency: str | None = None
    procurement_reference: str | None = None
    procurement_date: str | None = None
    supplier_entity_id: str | None = None
    product: str | None = None
    target_program: str | None = None
    contract_value: float | None = None
    currency: str = "USD"
    source_url: str | None = None
    source_excerpt: str | None = None
    investigation_id: str | None = None


class ShipmentInput(BaseModel):
    exporter_name: str
    exporter_country: str = "China"
    importer_entity_id: str | None = None
    importer_name: str
    product: str
    hs_code: str | None = None
    shipment_date: str | None = None
    weight_kg: float | None = None
    quantity: float | None = None
    quantity_unit: str | None = None
    origin_country: str = "China"
    destination_country: str = "United States"
    bill_no: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    raw_record: dict | None = None
    investigation_id: str | None = None


class AnalyzeInput(BaseModel):
    case_id: str | None = None
    model_id: str | None = None
    country: str = "United States"
    investigation_id: str | None = None


class ExpertDiscoveryInput(BaseModel):
    countries: list[str] = Field(
        default_factory=lambda: ["United States", "India", "Japan", "Taiwan"]
    )
    minimum_score: int = Field(default=60, ge=0, le=100)
    max_candidates: int = Field(default=20, ge=1, le=100)
    mcp_tools: list[str] = Field(default_factory=lambda: list(SUPPLY_CHAIN_MCP_TOOLS))
    model_id: str | None = None
    research_rounds: int = Field(default=3, ge=1, le=6)
    import_record_window_days: Literal[90, 180, 365] = 365


class SupplyChainMCPInput(BaseModel):
    case_id: str
    shipment_id: str
    tools: list[str] = Field(default_factory=lambda: list(SUPPLY_CHAIN_MCP_TOOLS))


class CandidateReviewInput(BaseModel):
    action: str = Field(pattern="^(approve|reject)$")
    note: str | None = Field(default=None, max_length=1000)


class ReportInput(BaseModel):
    case_ids: list[str] = Field(default_factory=list)
    model_id: str | None = None
    title: str | None = None
    country: str = "United States"
    investigation_id: str | None = None


@router.get("/dashboard")
def dashboard(
    country: str = "United States",
    investigation_id: str | None = None,
    db: Session = Depends(get_db),
):
    investigation = _get_investigation(db, country, investigation_id)
    case_query = db.query(
        SupplyChainCase.id, SupplyChainCase.supplier_entity_id
    ).filter(SupplyChainCase.country == country)
    if investigation:
        case_query = case_query.filter(
            SupplyChainCase.id.in_(investigation.case_ids or [])
        )
    case_rows = case_query.all()
    case_ids = [row[0] for row in case_rows]
    entity_ids = {row[1] for row in case_rows if row[1]}
    shipment_query = db.query(SupplyChainShipment)
    if investigation:
        shipment_query = shipment_query.filter(
            SupplyChainShipment.id.in_(investigation.shipment_ids or [])
        )
    else:
        shipment_query = shipment_query.filter(
            SupplyChainShipment.destination_country == country
        )
    shipment_rows = shipment_query.all()
    entity_ids.update(row.importer_entity_id for row in shipment_rows if row.importer_entity_id)
    if investigation:
        entity_ids.update(investigation.entity_ids or [])
    evidence_query = db.query(SupplyChainEvidence).filter(
        SupplyChainEvidence.case_id.in_(case_ids)
    )
    open_source_query = db.query(SupplyChainOpenSourceEvidence).filter(
        SupplyChainOpenSourceEvidence.case_id.in_(case_ids)
    )
    report_query = db.query(SupplyChainReport).filter(
        SupplyChainReport.country == country
    )
    if investigation:
        evidence_query = evidence_query.filter(
            SupplyChainEvidence.id.in_(investigation.evidence_ids or [])
        )
        open_source_query = open_source_query.filter(
            SupplyChainOpenSourceEvidence.id.in_(
                investigation.open_source_evidence_ids or []
            )
        )
        report_query = report_query.filter(
            SupplyChainReport.id.in_(investigation.report_ids or [])
        )
    return {
        "country": country,
        "investigation_id": investigation_id,
        "entities": len(entity_ids),
        "cases": len(case_rows),
        "shipments": len(shipment_rows),
        "evidence": evidence_query.count() if case_ids else 0,
        "open_source_evidence": open_source_query.count() if case_ids else 0,
        "reportable": evidence_query.filter(
            SupplyChainEvidence.is_reportable == True,
        ).count() if case_ids else 0,
        "reports": report_query.count(),
    }


@router.get("/entities")
def list_entities(
    country: str | None = None,
    investigation_id: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(SupplyChainEntity)
    investigation = _get_investigation(db, country or "", investigation_id)
    if investigation:
        query = query.filter(SupplyChainEntity.id.in_(investigation.entity_ids or []))
    elif country:
        query = query.filter(SupplyChainEntity.country == country)
    rows = query.order_by(SupplyChainEntity.created_at.desc()).all()
    return [_dump(row, ENTITY_FIELDS) for row in rows]


@router.post("/entities")
def create_entity(data: EntityInput, db: Session = Depends(get_db)):
    values = data.model_dump()
    investigation_id = values.pop("investigation_id")
    row = SupplyChainEntity(id=f"ent-{uuid4().hex[:12]}", **values)
    db.add(row)
    _attach(db, investigation_id, "entity_ids", row.id)
    db.commit()
    db.refresh(row)
    return _dump(row, ENTITY_FIELDS)


@router.get("/cases")
def list_cases(
    country: str = "United States",
    investigation_id: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(SupplyChainCase).filter(
        SupplyChainCase.country == country
    )
    investigation = _get_investigation(db, country, investigation_id)
    if investigation:
        query = query.filter(SupplyChainCase.id.in_(investigation.case_ids or []))
    rows = query.order_by(SupplyChainCase.created_at.desc()).all()
    return [_dump(row, CASE_FIELDS) for row in rows]


@router.post("/cases")
def create_case(data: CaseInput, db: Session = Depends(get_db)):
    values = data.model_dump()
    investigation_id = values.pop("investigation_id")
    values["procurement_date"] = _parse_date(values["procurement_date"])
    row = SupplyChainCase(id=f"case-{uuid4().hex[:12]}", **values)
    db.add(row)
    _attach(db, investigation_id, "case_ids", row.id)
    if row.supplier_entity_id:
        _attach(db, investigation_id, "entity_ids", row.supplier_entity_id)
    db.commit()
    db.refresh(row)
    return _dump(row, CASE_FIELDS)


@router.get("/shipments")
def list_shipments(
    country: str = "United States",
    investigation_id: str | None = None,
    db: Session = Depends(get_db),
):
    investigation = _get_investigation(db, country, investigation_id)
    query = db.query(SupplyChainShipment)
    if investigation:
        query = query.filter(
            SupplyChainShipment.id.in_(investigation.shipment_ids or [])
        )
    else:
        query = query.filter(
            SupplyChainShipment.destination_country == country
        )
    rows = query.order_by(
        SupplyChainShipment.shipment_date.desc()
    ).all()
    return [_dump(row, SHIPMENT_FIELDS) for row in rows]


@router.post("/shipments")
def create_shipment(data: ShipmentInput, db: Session = Depends(get_db)):
    values = data.model_dump()
    investigation_id = values.pop("investigation_id")
    values["shipment_date"] = _parse_date(values["shipment_date"])
    row = SupplyChainShipment(id=f"shp-{uuid4().hex[:12]}", **values)
    db.add(row)
    _attach(db, investigation_id, "shipment_ids", row.id)
    if row.importer_entity_id:
        _attach(db, investigation_id, "entity_ids", row.importer_entity_id)
    db.commit()
    db.refresh(row)
    return _dump(row, SHIPMENT_FIELDS)


@router.get("/evidence")
def list_evidence(
    country: str = "United States",
    investigation_id: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(SupplyChainEvidence).join(
        SupplyChainCase, SupplyChainCase.id == SupplyChainEvidence.case_id
    ).filter(SupplyChainCase.country == country)
    investigation = _get_investigation(db, country, investigation_id)
    if investigation:
        query = query.filter(
            SupplyChainEvidence.id.in_(investigation.evidence_ids or [])
        )
    rows = query.order_by(
        SupplyChainEvidence.score.desc(), SupplyChainEvidence.created_at.desc()
    ).all()
    return [_dump(row, EVIDENCE_FIELDS) for row in rows]


@router.get("/open-source-evidence")
def list_open_source_evidence(
    country: str = "United States",
    investigation_id: str | None = None,
    db: Session = Depends(get_db),
):
    investigation = _get_investigation(db, country, investigation_id)
    if investigation:
        # Investigation-level evidence may intentionally have no case_id.  Its
        # explicit attachment to the investigation is the scoping boundary.
        query = db.query(SupplyChainOpenSourceEvidence).filter(
            SupplyChainOpenSourceEvidence.id.in_(
                investigation.open_source_evidence_ids or []
            )
        )
    else:
        query = db.query(SupplyChainOpenSourceEvidence).join(
            SupplyChainCase,
            SupplyChainCase.id == SupplyChainOpenSourceEvidence.case_id,
        ).filter(SupplyChainCase.country == country)
    rows = query.order_by(
        SupplyChainOpenSourceEvidence.evidence_grade,
        SupplyChainOpenSourceEvidence.created_at.desc(),
    ).all()
    return [_dump(row, OPEN_SOURCE_EVIDENCE_FIELDS) for row in rows]


def _related_entity_ids(db: Session, entity_id: str | None) -> set[str]:
    if not entity_id:
        return set()
    related = {entity_id}
    entity = db.get(SupplyChainEntity, entity_id)
    if entity and entity.parent_id:
        related.add(entity.parent_id)
    children = db.query(SupplyChainEntity).filter(
        SupplyChainEntity.parent_id.in_(related)
    ).all()
    related.update(child.id for child in children)
    return related


def _score_pair(case: SupplyChainCase, shipment: SupplyChainShipment, direct: bool):
    facts = {
        "china_origin": (shipment.origin_country or shipment.exporter_country) == "China",
        "same_or_related_importer": direct,
        "procurement_date": case.procurement_date.isoformat() if case.procurement_date else None,
        "shipment_date": shipment.shipment_date.isoformat() if shipment.shipment_date else None,
        "product_overlap": False,
    }
    score = 20 if facts["china_origin"] else 0
    score += 35 if direct else 0
    if case.procurement_date and shipment.shipment_date:
        days = abs((shipment.shipment_date - case.procurement_date).days)
        if days <= 180:
            score += 20
        elif days <= 365:
            score += 10
        facts["date_distance_days"] = days
    case_terms = {_norm(v) for v in re.split(r"[\s,;/]+", case.product or "") if len(v) > 1}
    shipment_text = _norm(shipment.product)
    overlap = any(term and term in shipment_text for term in case_terms)
    facts["product_overlap"] = overlap
    if overlap:
        score += 25
    grade = "A" if score >= 85 else "B" if score >= 60 else "C"
    return score, grade, facts


def _build_discovery_candidates(
    cases: list[SupplyChainCase],
    shipments: list[SupplyChainShipment],
    entities: list[SupplyChainEntity],
    minimum_score: int,
    enabled_tools: list[str] | None = None,
) -> list[dict]:
    """Find China-origin imports crossing a named defence supplier.

    Discovery deliberately stops at candidate status. A match identifies a
    research direction; it does not claim that the shipment entered the
    military programme.
    """
    enabled = set(enabled_tools if enabled_tools is not None else SUPPLY_CHAIN_MCP_TOOLS)
    entity_by_id = {entity.id: entity for entity in entities}
    children_by_parent: dict[str, set[str]] = {}
    for entity in entities:
        if entity.parent_id:
            children_by_parent.setdefault(entity.parent_id, set()).add(entity.id)

    candidates: list[dict] = []
    for case in cases:
        if not case.supplier_entity_id:
            continue
        related_ids = {case.supplier_entity_id}
        supplier = entity_by_id.get(case.supplier_entity_id)
        if supplier and supplier.parent_id:
            related_ids.add(supplier.parent_id)
        for entity_id in tuple(related_ids):
            related_ids.update(children_by_parent.get(entity_id, set()))
        related_names = {
            _norm(name)
            for entity_id in related_ids
            for entity in [entity_by_id.get(entity_id)]
            if entity
            for name in [entity.name, entity.name_zh, *(entity.aliases or [])]
            if name
        }

        for shipment in shipments:
            china_origin = (
                shipment.origin_country or shipment.exporter_country
            ) == "China"
            direct = (
                shipment.importer_entity_id in related_ids
                or _norm(shipment.importer_name) in related_names
            )
            if not china_origin or not direct:
                continue
            score, _, facts = _score_pair(case, shipment, direct=True)
            supplier_entity = entity_by_id.get(case.supplier_entity_id)
            mcp_checks = _evaluate_mcp_evidence(
                case, shipment, supplier_entity, enabled,
            )
            score = _apply_mcp_score_gates(score, mcp_checks)
            grade = "A" if score >= 85 else "B" if score >= 60 else "C"
            facts["mcp_checks"] = mcp_checks
            if score < minimum_score:
                continue
            candidates.append({
                "case_id": case.id,
                "shipment_id": shipment.id,
                "country": case.country,
                "supplier_entity_id": case.supplier_entity_id,
                "title": case.title,
                "target_program": case.target_program,
                "exporter_name": shipment.exporter_name,
                "importer_name": shipment.importer_name,
                "product": shipment.product,
                "score": score,
                "evidence_grade": grade,
                "verified_facts": facts,
            })
    return sorted(candidates, key=lambda item: item["score"], reverse=True)


def _part_numbers(value: str | None) -> set[str]:
    if not value:
        return set()
    return {
        token.upper()
        for token in re.findall(r"\b(?=[A-Z0-9-]{5,}\b)(?=[A-Z0-9-]*\d)[A-Z0-9]+(?:-[A-Z0-9]+)+\b", value.upper())
    }


def _evaluate_mcp_evidence(
    case: SupplyChainCase,
    shipment: SupplyChainShipment,
    supplier: SupplyChainEntity | None,
    enabled_tools: set[str],
) -> dict:
    case_parts = _part_numbers(" ".join(filter(None, [case.title, case.product, case.target_program, case.source_excerpt])))
    shipment_parts = _part_numbers(shipment.product)
    return {
        "entity_resolved": (
            "resolve_supply_chain_entity" in enabled_tools
            and bool(shipment.importer_entity_id and supplier and supplier.id == shipment.importer_entity_id)
        ),
        "contract_source_verified": (
            "search_supply_chain_contracts" in enabled_tools
            and bool(case.procurement_reference and case.source_url)
        ),
        "trade_batch_verified": (
            "search_supply_chain_trade_records" in enabled_tools
            and bool(shipment.bill_no and shipment.source_url)
        ),
        "part_number_match": (
            "search_supply_chain_part_numbers" in enabled_tools
            and bool(case_parts & shipment_parts)
        ),
        "matched_part_numbers": sorted(case_parts & shipment_parts),
        "end_use_verified": (
            "verify_supply_chain_end_use" in enabled_tools
            and bool(case.target_program and case.source_url and case.source_excerpt)
        ),
        "enabled_tools": sorted(enabled_tools),
    }


def _apply_mcp_score_gates(score: int, checks: dict) -> int:
    gated = score
    if not checks["entity_resolved"]:
        gated = min(gated, 69)
    if not checks["contract_source_verified"]:
        gated = min(gated, 74)
    if not checks["trade_batch_verified"]:
        gated = min(gated, 79)
    if not checks["part_number_match"]:
        gated = min(gated, 84)
    if checks["end_use_verified"] and checks["part_number_match"]:
        gated = min(100, gated + 5)
    return gated


async def _model_review(
    model: ModelConfig, case: SupplyChainCase, shipment: SupplyChainShipment,
    grade: str, score: int, facts: dict,
) -> dict:
    prompt = f"""
你是军工供应链开源情报证据审核员。请审核一条{case.country}军用采购项目与自华进口记录的关联。
采购项目：{case.title}
采购机关：{case.procurement_agency or "未提供"}
供应商：{case.supplier_entity_id or "未提供"}
采购产品：{case.product or "未提供"}
目标项目或用途：{case.target_program or "未提供"}
采购日期：{case.procurement_date or "未提供"}
采购原文摘录：{case.source_excerpt or "未提供"}
进口商：{shipment.importer_name}
中国出口商：{shipment.exporter_name}
进口货物：{shipment.product}
运输日期：{shipment.shipment_date or "未提供"}
原产地：{shipment.origin_country or shipment.exporter_country}
规则初评：{grade}级，{score}分；事实字段：{json.dumps(facts, ensure_ascii=False)}

只依据上述字段判断，不得虚构最终用途。A级仅限直接证据证明货物进入具体军工项目；
B级表示企业、产品和时间高度关联；C级表示仅构成待核线索。
返回JSON对象，并在JSON后补充不少于100字的中文审核说明：
{{"grade":"A|B|C","status":"approved|needs_review|rejected","reportable":true,
"relation_type":"direct_supply|processed_supply|possible_supply",
"reason":"简明理由","limitations":["证据缺口"]}}
""".strip()
    result = await call_llm(model, prompt, timeout_seconds=180)
    content = result["content"]
    match = re.search(r"\{.*?\}", content, re.S)
    if not match:
        raise ValueError("模型未返回可解析的证据审核结果")
    review = json.loads(match.group(0))
    review["narrative"] = content
    return review


@router.post("/experts/discover")
async def discover_supply_chains(data: ExpertDiscoveryInput, db: Session = Depends(get_db)):
    model = db.get(ModelConfig, data.model_id) if data.model_id else get_default_model(db)
    if not model:
        raise HTTPException(400, "请先配置默认研究模型，联网供应链发现需要模型完成证据交叉核验")
    if not model.is_active:
        raise HTTPException(400, "所选研究模型未启用")
    expert_prompt, prompt_template_id = resolve_supply_chain_expert_prompt(db)
    online = await discover_online_supply_chains(
        data.countries, data.mcp_tools, model, data.max_candidates,
        research_rounds=data.research_rounds,
        import_record_window_days=data.import_record_window_days,
        expert_prompt=expert_prompt,
        prompt_template_id=prompt_template_id,
        search_configs=_configured_supply_chain_search_sources(db),
    )
    existing_rows = db.query(SupplyChainDiscoveryCandidate).all()
    existing_by_pair = {}
    for row in existing_rows:
        originals = (row.verified_facts or {}).get("original_fields") or {}
        pair = (
            row.country,
            _norm(originals.get("importer_name") or row.importer_name),
            _norm(originals.get("product") or row.product),
        )
        existing_by_pair[pair] = row
    existing_chain_signatures = [
        (row.destination_country, row.importer_name, row.product)
        for row in db.query(SupplyChainShipment).all()
    ]
    for case in db.query(SupplyChainCase).all():
        supplier = db.get(SupplyChainEntity, case.supplier_entity_id) if case.supplier_entity_id else None
        if supplier:
            existing_chain_signatures.append((case.country, supplier.name, case.product))
            existing_chain_signatures.extend(
                (case.country, alias, case.product) for alias in (supplier.aliases or [])
            )
    existing_evidence_urls = {
        url for (url,) in db.query(SupplyChainOpenSourceEvidence.source_url).filter(
            SupplyChainOpenSourceEvidence.source_url.isnot(None)
        ).all() if url
    }
    existing_evidence_urls.update(
        url for (url,) in db.query(SupplyChainCase.source_url).filter(
            SupplyChainCase.source_url.isnot(None)
        ).all() if url
    )
    duplicates_skipped = 0
    created: list[SupplyChainDiscoveryCandidate] = []
    for item in online["candidates"]:
        originals = item.get("original_fields") or {}
        pair = (
            item["country"],
            _norm(originals.get("importer_name") or item["importer_name"]),
            _norm(originals.get("product") or item["product"]),
        )
        evidence_status = item.get("evidence_status") or "closed"
        score = min(95, max(60, int(item.get("confidence_score", 0))))
        if evidence_status != "closed":
            score = min(score, 74)
        if score < data.minimum_score:
            continue
        existing = existing_by_pair.get(pair)
        if existing:
            duplicates_skipped += 1
            if existing.status == "rejected":
                continue
            facts = dict(existing.verified_facts or {})
            prior_validation = facts.get("evidence_validation") or {}
            prior_trade_valid = bool((prior_validation.get("trade") or {}).get("valid"))
            contract_url = facts.get("contract_evidence_url") or item.get("contract_evidence_url")
            trade_url = (
                facts.get("trade_evidence_url") if prior_trade_valid
                else None
            ) or item.get("trade_evidence_url")
            combined_status = "closed" if contract_url and trade_url else (
                "contract_only" if contract_url else "trade_only"
            )
            facts.update({
                "contract_evidence_url": contract_url,
                "trade_evidence_url": trade_url,
                "evidence_status": combined_status,
                "evidence_gap": (
                    "" if combined_status == "closed"
                    else item.get("evidence_gap") or "待补所选时间范围内的中国进口记录、提单或中国供应商证据" if combined_status == "contract_only"
                    else "待补军工合同、采购项目或最终用途证据"
                ),
                "supporting_urls": list(dict.fromkeys([
                    *(facts.get("supporting_urls") or []), *(item.get("supporting_urls") or []),
                ])),
                "limitations": item.get("limitations") or facts.get("limitations") or [],
                "evidence_validation": item.get("evidence_validation") or facts.get("evidence_validation") or {},
                "contract_date": item.get("contract_date") or facts.get("contract_date"),
                "trade_date": item.get("trade_date") or facts.get("trade_date"),
                "import_record_window_days": data.import_record_window_days,
                "research_trace": online.get("research_trace") or {},
            })
            existing.verified_facts = facts
            existing.score = max(existing.score or 0, score if combined_status != "closed" else max(75, score))
            existing.evidence_grade = "B" if combined_status == "closed" else "C"
            existing.title = item["contract_title"]
            existing.importer_name = item["importer_name"]
            existing.exporter_name = item["exporter_name"]
            existing.product = item["product"]
            entity = db.get(SupplyChainEntity, existing.supplier_entity_id)
            if entity:
                entity.name = item["importer_name"]
                entity.source_url = contract_url or trade_url or entity.source_url
            if item.get("contract_evidence_url"):
                case = db.get(SupplyChainCase, existing.case_id)
                if case:
                    case.title = item["contract_title"]
                    case.procurement_agency = item.get("contracting_agency") or case.procurement_agency
                    case.procurement_reference = item.get("contract_reference") or case.procurement_reference
                    case.procurement_date = _parse_online_date(item.get("contract_date")) or case.procurement_date
                    case.product = item["product"]
                    case.target_program = item.get("target_program") or case.target_program
                    case.source_url = item["contract_evidence_url"]
                    case.source_excerpt = item.get("contract_excerpt") or case.source_excerpt
                has_contract_evidence = db.query(SupplyChainOpenSourceEvidence.id).filter(
                    SupplyChainOpenSourceEvidence.case_id == existing.case_id,
                    SupplyChainOpenSourceEvidence.source_type == "official_contract",
                ).first()
                if not has_contract_evidence:
                    db.add(SupplyChainOpenSourceEvidence(
                        id=f"ose-online-contract-{uuid4().hex[:12]}",
                        case_id=existing.case_id,
                        title="国防合同或官方项目证据",
                        source_type="official_contract",
                        source_url=item["contract_evidence_url"],
                        source_excerpt=item.get("contract_excerpt"),
                        verified_facts=[item["contract_title"]],
                        evidence_grade="B", status="follow_up",
                        limitations=item.get("limitations") or [],
                    ))
            if item.get("trade_evidence_url"):
                shipment = db.get(SupplyChainShipment, existing.shipment_id)
                if shipment:
                    shipment.source_url = item["trade_evidence_url"]
                    shipment.bill_no = item.get("trade_reference") or shipment.bill_no
                    shipment.exporter_name = item["exporter_name"]
                    shipment.importer_name = item["importer_name"]
                    shipment.product = item["product"]
                    shipment.shipment_date = _parse_online_date(item.get("trade_date")) or shipment.shipment_date
                    shipment.raw_record = {
                        **(shipment.raw_record or {}),
                        "excerpt": item.get("trade_excerpt"),
                        "trade_date_basis": item.get("trade_date_basis"),
                        "evidence_validation": item.get("evidence_validation") or {},
                    }
                existing.exporter_name = item["exporter_name"]
                has_trade_evidence = db.query(SupplyChainOpenSourceEvidence.id).filter(
                    SupplyChainOpenSourceEvidence.case_id == existing.case_id,
                    SupplyChainOpenSourceEvidence.source_type == "trade_record",
                ).first()
                if not has_trade_evidence:
                    db.add(SupplyChainOpenSourceEvidence(
                        id=f"ose-online-trade-{uuid4().hex[:12]}",
                        case_id=existing.case_id,
                        title="中国来源进口或贸易证据",
                        source_type="trade_record",
                        source_url=item["trade_evidence_url"],
                        source_excerpt=item.get("trade_excerpt"),
                        verified_facts=[item["exporter_name"], item["product"]],
                        evidence_grade="B", status="follow_up",
                        limitations=item.get("limitations") or [],
                    ))
            continue
        original_importer = originals.get("importer_name") or item["importer_name"]
        original_product = originals.get("product") or item["product"]
        duplicate_chain = any(
            country == item["country"] and _chain_signature_matches(
                original_importer, original_product, known_importer, known_product,
            )
            for country, known_importer, known_product in existing_chain_signatures
        )
        incoming_urls = {
            item.get("contract_evidence_url"), item.get("trade_evidence_url"),
        } - {None, ""}
        if duplicate_chain or bool(incoming_urls & existing_evidence_urls):
            duplicates_skipped += 1
            continue
        token = uuid4().hex[:12]
        primary_url = item.get("contract_evidence_url") or item.get("trade_evidence_url")
        entity = SupplyChainEntity(
            id=f"ent-online-{token}", name=item["importer_name"], country=item["country"],
            entity_type="defense_supplier", source_url=primary_url,
            notes="联网供应链专家发现，待人工审核。",
        )
        db.add(entity)
        db.flush()
        case = SupplyChainCase(
            id=f"case-online-{token}", country=item["country"], title=item["contract_title"],
            procurement_agency=item.get("contracting_agency"),
            procurement_reference=item.get("contract_reference"), supplier_entity_id=entity.id,
            product=item["product"], target_program=item.get("target_program"),
            procurement_date=_parse_online_date(item.get("contract_date")),
            source_url=item.get("contract_evidence_url"), source_excerpt=item.get("contract_excerpt"),
            status="needs_review",
        )
        shipment = SupplyChainShipment(
            id=f"shp-online-{token}", exporter_name=item["exporter_name"], exporter_country="China",
            importer_entity_id=entity.id, importer_name=item["importer_name"], product=item["product"],
            origin_country="China", destination_country=item["country"],
            shipment_date=_parse_online_date(item.get("trade_date")),
            bill_no=item.get("trade_reference"), source_name="联网公开来源",
            source_url=item.get("trade_evidence_url"), raw_record={
                "excerpt": item.get("trade_excerpt"),
                "trade_date_basis": item.get("trade_date_basis"),
                "evidence_validation": item.get("evidence_validation") or {},
            },
        )
        db.add_all([case, shipment])
        db.flush()
        source_rows = [
            SupplyChainOpenSourceEvidence(
                id=f"ose-online-contract-{token}", case_id=case.id, title="国防合同或官方项目证据",
                source_type="official_contract", source_url=item["contract_evidence_url"],
                source_excerpt=item.get("contract_excerpt"), verified_facts=[item["contract_title"]],
                evidence_grade="B", status="follow_up", limitations=item.get("limitations") or [],
            ),
            SupplyChainOpenSourceEvidence(
                id=f"ose-online-trade-{token}", case_id=case.id, title="中国来源进口或贸易证据",
                source_type="trade_record", source_url=item["trade_evidence_url"],
                source_excerpt=item.get("trade_excerpt"), verified_facts=[item["exporter_name"], item["product"]],
                evidence_grade="B", status="follow_up", limitations=item.get("limitations") or [],
            ),
        ]
        source_rows = [row for row in source_rows if row.source_url]
        facts = {
            "online_research": True, "evidence_status": evidence_status,
            "evidence_gap": item.get("evidence_gap") or "",
            "contract_evidence_url": item.get("contract_evidence_url"),
            "trade_evidence_url": item.get("trade_evidence_url"),
            "supporting_urls": item.get("supporting_urls") or [], "limitations": item.get("limitations") or [],
            "evidence_validation": item.get("evidence_validation") or {},
            "contract_date": item.get("contract_date"), "trade_date": item.get("trade_date"),
            "trade_date_basis": item.get("trade_date_basis"),
            "import_record_window_days": data.import_record_window_days,
            "original_fields": item.get("original_fields") or {},
            "research_trace": online.get("research_trace") or {},
        }
        candidate = SupplyChainDiscoveryCandidate(
            id=f"candidate-online-{token}", country=item["country"], case_id=case.id,
            shipment_id=shipment.id, supplier_entity_id=entity.id, title=item["contract_title"],
            target_program=item.get("target_program"), exporter_name=item["exporter_name"],
            importer_name=item["importer_name"], product=item["product"], score=score,
            evidence_grade=("C" if evidence_status != "closed" else "A" if score >= 85 else "B"),
            verified_facts=facts, status="pending",
        )
        db.add_all([*source_rows, candidate])
        created.append(candidate)
        existing_by_pair[pair] = candidate
    db.commit()
    return {
        "cases_scanned": online["sources_found"], "shipments_scanned": online["sources_read"],
        "candidates_matched": len(online["candidates"]), "candidates_created": len(created),
        "duplicates_skipped": duplicates_skipped,
        "discoveries": [_dump(row, CANDIDATE_FIELDS) for row in created],
        "search_errors": online["errors"],
        "research_trace": online.get("research_trace") or {},
    }


@router.get("/experts/mcp-tools")
def list_supply_chain_mcp_tools():
    labels = {
        "resolve_supply_chain_entity": ("企业身份消歧", "核验进口主体与军工供应商的法定主体关系"),
        "search_supply_chain_contracts": ("军工合同检索", "核验合同号、采购机关与官方原始来源"),
        "search_supply_chain_trade_records": ("贸易记录检索", "核验提单号、批次与贸易原始来源"),
        "deep_search_china_trade_records": ("中国进口与提单深度检索", "按企业别名、地址、产品和时间定向穿透专业贸易数据索引"),
        "search_supply_chain_part_numbers": ("精确料号检索", "匹配P/N、NSN、图号与具体型号"),
        "verify_supply_chain_end_use": ("最终用途核验", "核验目标平台、合同用途与原始文件"),
    }
    return [
        {"id": tool, "name": labels[tool][0], "description": labels[tool][1], "is_active": True}
        for tool in SUPPLY_CHAIN_MCP_TOOLS
    ]


@router.post("/mcp/evaluate")
def evaluate_supply_chain_pair(data: SupplyChainMCPInput, db: Session = Depends(get_db)):
    case = db.get(SupplyChainCase, data.case_id)
    shipment = db.get(SupplyChainShipment, data.shipment_id)
    if not case or not shipment:
        raise HTTPException(404, "采购项目或贸易记录不存在")
    supplier = db.get(SupplyChainEntity, case.supplier_entity_id) if case.supplier_entity_id else None
    tools = {tool for tool in data.tools if tool in SUPPLY_CHAIN_MCP_TOOLS}
    direct = bool(
        shipment.importer_entity_id == case.supplier_entity_id
        or (supplier and _norm(shipment.importer_name) in {
            _norm(name) for name in [supplier.name, supplier.name_zh, *(supplier.aliases or [])] if name
        })
    )
    base_score, _, facts = _score_pair(case, shipment, direct)
    checks = _evaluate_mcp_evidence(case, shipment, supplier, tools)
    score = _apply_mcp_score_gates(base_score, checks)
    return {
        "case_id": case.id,
        "shipment_id": shipment.id,
        "base_score": base_score,
        "score": score,
        "evidence_grade": "A" if score >= 85 else "B" if score >= 60 else "C",
        "checks": checks,
        "facts": facts,
    }


@router.get("/experts/candidates")
def list_discovery_candidates(
    status: str | None = None, db: Session = Depends(get_db),
):
    query = db.query(SupplyChainDiscoveryCandidate)
    if status:
        query = query.filter(SupplyChainDiscoveryCandidate.status == status)
    rows = query.order_by(SupplyChainDiscoveryCandidate.created_at.desc()).all()
    return [_dump(row, CANDIDATE_FIELDS) for row in rows]


@router.post("/experts/candidates/{candidate_id}/review")
def review_discovery_candidate(
    candidate_id: str, data: CandidateReviewInput, db: Session = Depends(get_db),
):
    candidate = db.get(SupplyChainDiscoveryCandidate, candidate_id)
    if not candidate:
        raise HTTPException(404, "候选链不存在")
    if candidate.status != "pending":
        raise HTTPException(409, "该候选链已经审核")
    candidate.review_note = data.note
    candidate.reviewed_at = _now()
    if data.action == "reject":
        candidate.status = "rejected"
        db.commit()
        return _dump(candidate, CANDIDATE_FIELDS)

    investigation_id = f"inv-expert-{uuid4().hex[:12]}"
    evidence_id = f"evd-{uuid4().hex[:12]}"
    open_source_ids = [
        row[0] for row in db.query(SupplyChainOpenSourceEvidence.id).filter(
            SupplyChainOpenSourceEvidence.case_id == candidate.case_id
        ).all()
    ]
    case = db.get(SupplyChainCase, candidate.case_id)
    importer = db.get(SupplyChainEntity, candidate.supplier_entity_id) if candidate.supplier_entity_id else None
    facts = candidate.verified_facts or {}
    contract_url = facts.get("contract_evidence_url") or (case.source_url if case else None)
    shipment = db.get(SupplyChainShipment, candidate.shipment_id)
    trade_url = facts.get("trade_evidence_url") or (shipment.source_url if shipment else None)

    exporter = db.query(SupplyChainEntity).filter(
        SupplyChainEntity.country == "China",
        SupplyChainEntity.name == candidate.exporter_name,
    ).first()
    if not exporter:
        exporter = SupplyChainEntity(
            id=f"ent-expert-exporter-{uuid4().hex[:12]}", name=candidate.exporter_name,
            country="China", entity_type="china_exporter", source_url=trade_url,
            defense_roles=[f"向{candidate.importer_name}供应{candidate.product}"],
            notes="由联网贸易证据识别的中国上游供应节点，待进一步核验法定主体。",
        )
        db.add(exporter)
    elif candidate.product not in (exporter.defense_roles or []):
        exporter.defense_roles = [*(exporter.defense_roles or []), candidate.product]

    if importer:
        importer.entity_type = "defense_supplier"
        importer.defense_roles = list(dict.fromkeys([
            *(importer.defense_roles or []),
            *(filter(None, [case.target_program if case else None, case.product if case else None])),
        ]))

    agency = None
    if case and case.procurement_agency:
        agency = db.query(SupplyChainEntity).filter(
            SupplyChainEntity.country == candidate.country,
            SupplyChainEntity.name == case.procurement_agency,
        ).first()
        if not agency:
            agency = SupplyChainEntity(
                id=f"ent-expert-agency-{uuid4().hex[:12]}", name=case.procurement_agency,
                country=candidate.country, entity_type="government_agency", source_url=contract_url,
                defense_roles=[case.target_program or case.title],
                notes="合同或官方项目来源中识别的采购/最终应用机关。",
            )
            db.add(agency)

    entity_ids = list(dict.fromkeys([
        *(filter(None, [candidate.supplier_entity_id, exporter.id, agency.id if agency else None])),
    ]))
    report_id = f"scr-expert-{uuid4().hex[:12]}"
    report = SupplyChainReport(
        id=report_id, country=candidate.country,
        title=f"{candidate.importer_name}中国来源供应链初核报告",
        case_ids=[candidate.case_id], evidence_ids=[evidence_id], model_id="supply-chain-online-expert",
        status="needs_review",
        summary=f"联网证据显示{candidate.exporter_name}向{candidate.importer_name}供应{candidate.product}；同时存在与{candidate.title}相关的合同或官方项目来源。",
        content=(
            f"# {candidate.importer_name}中国来源供应链初核\n\n"
            f"- 中国上游：{candidate.exporter_name}\n"
            f"- 进口/军工企业：{candidate.importer_name}\n"
            f"- 产品：{candidate.product}\n"
            f"- 合同或项目：{candidate.title}\n"
            f"- 应用方向：{candidate.target_program or '待进一步核验'}\n\n"
            f"## 证据来源\n\n"
            f"- [合同或官方项目证据]({contract_url})\n"
            f"- [中国进口或贸易证据]({trade_url})\n\n"
            "## 证据边界\n\n本报告为审核通过后的初始归档，不代表已证明具体进口批次进入最终装备；仍需核验料号、BOM、批次和最终用途。"
        ),
        generated_at=_now(),
    )
    direction = COUNTRY_NAMES.get(candidate.country, candidate.country)
    investigation = SupplyChainInvestigation(
        id=investigation_id,
        country=candidate.country,
        name=f"{direction}·{candidate.importer_name}中国供应线索",
        description=(
            f"审核通过的专家候选：{candidate.exporter_name}向"
            f"{candidate.importer_name}供应{candidate.product}，并与"
            f"“{candidate.title}”形成企业级交叉。尚需核验精确料号、"
            "批次、BOM和最终用途。"
        ),
        status="researching",
        entity_ids=entity_ids,
        case_ids=[candidate.case_id],
        shipment_ids=[candidate.shipment_id],
        evidence_ids=[evidence_id],
        open_source_evidence_ids=open_source_ids,
        report_ids=[report_id],
    )
    evidence = SupplyChainEvidence(
        id=evidence_id,
        case_id=candidate.case_id,
        shipment_id=candidate.shipment_id,
        relation_type="possible_supply",
        evidence_grade=candidate.evidence_grade,
        score=candidate.score,
        status="needs_review",
        reasoning=(
            "候选链已通过人工初审并进入供应链穿透模块。该结果仍不能证明"
            "货物已进入具体军工项目，需继续补充精确料号、批次和最终用途证据。"
        ),
        verified_facts=candidate.verified_facts,
        model_review={"source": "supply_chain_expert", "human_approved": True},
        is_reportable=False,
    )
    candidate.status = "approved"
    candidate.investigation_id = investigation_id
    db.add_all([investigation, evidence, report])
    db.commit()
    return _dump(candidate, CANDIDATE_FIELDS)


@router.post("/analyze")
async def analyze(data: AnalyzeInput, db: Session = Depends(get_db)):
    investigation = _get_investigation(db, data.country, data.investigation_id)
    case_query = db.query(SupplyChainCase).filter(
        SupplyChainCase.country == data.country
    )
    if investigation:
        case_query = case_query.filter(
            SupplyChainCase.id.in_(investigation.case_ids or [])
        )
    if data.case_id:
        case_query = case_query.filter(SupplyChainCase.id == data.case_id)
    cases = case_query.all()
    if not cases:
        raise HTTPException(404, "当前供应链项目没有可分析的采购项目")

    model = db.get(ModelConfig, data.model_id) if data.model_id else get_default_model(db)
    shipment_query = db.query(SupplyChainShipment).filter(
        SupplyChainShipment.destination_country == data.country
    )
    if investigation:
        shipment_query = shipment_query.filter(
            SupplyChainShipment.id.in_(investigation.shipment_ids or [])
        )
    shipments = shipment_query.all()
    created = []
    for case in cases:
        related_ids = _related_entity_ids(db, case.supplier_entity_id)
        related_entities = [
            db.get(SupplyChainEntity, entity_id) for entity_id in related_ids
        ]
        related_names = {
            _norm(name)
            for entity in related_entities if entity
            for name in [entity.name, entity.name_zh, *(entity.aliases or [])]
            if name
        }
        for shipment in shipments:
            direct = (
                shipment.importer_entity_id in related_ids
                or _norm(shipment.importer_name) in related_names
            )
            if not direct:
                continue
            exists = db.query(SupplyChainEvidence).filter(
                SupplyChainEvidence.case_id == case.id,
                SupplyChainEvidence.shipment_id == shipment.id,
            ).first()
            if exists:
                continue
            score, grade, facts = _score_pair(case, shipment, direct)
            reasoning = (
                f"进口主体与采购供应商或其关联企业匹配；规则评分{score}分。"
                "该结论仅说明供应链关联，是否用于具体军工项目仍需原始证据验证。"
            )
            review = None
            status = "pending"
            reportable = False
            relation_type = "possible_supply"
            if model and model.is_active:
                try:
                    review = await _model_review(model, case, shipment, grade, score, facts)
                    grade = review.get("grade", grade)
                    status = review.get("status", "needs_review")
                    reportable = bool(review.get("reportable", False))
                    relation_type = review.get("relation_type", relation_type)
                    reasoning = review.get("reason") or reasoning
                except Exception as exc:
                    review = {"error": str(exc)}
                    status = "needs_review"
            row = SupplyChainEvidence(
                id=f"evd-{uuid4().hex[:12]}", case_id=case.id, shipment_id=shipment.id,
                relation_type=relation_type, evidence_grade=grade, score=score,
                status=status, reasoning=reasoning, verified_facts=facts,
                model_review=review, is_reportable=reportable,
            )
            db.add(row)
            _attach(db, data.investigation_id, "evidence_ids", row.id)
            created.append(row)
    db.commit()
    return {
        "cases_scanned": len(cases), "shipments_scanned": len(shipments),
        "evidence_created": len(created),
        "evidence": [_dump(row, EVIDENCE_FIELDS) for row in created],
    }


@router.get("/reports")
def list_reports(
    country: str = "United States",
    investigation_id: str | None = None,
    db: Session = Depends(get_db),
):
    query = db.query(SupplyChainReport).filter(
        SupplyChainReport.country == country
    )
    investigation = _get_investigation(db, country, investigation_id)
    if investigation:
        query = query.filter(
            SupplyChainReport.id.in_(investigation.report_ids or [])
        )
    rows = query.order_by(
        SupplyChainReport.created_at.desc()
    ).all()
    return [_dump(row, REPORT_FIELDS) for row in rows]


@router.post("/reports/generate")
async def generate_report(data: ReportInput, db: Session = Depends(get_db)):
    investigation = _get_investigation(db, data.country, data.investigation_id)
    case_query = db.query(SupplyChainCase).filter(
        SupplyChainCase.country == data.country
    )
    if investigation:
        case_query = case_query.filter(
            SupplyChainCase.id.in_(investigation.case_ids or [])
        )
    if data.case_ids:
        case_query = case_query.filter(SupplyChainCase.id.in_(data.case_ids))
    cases = case_query.all()
    if not cases:
        raise HTTPException(400, "请先录入并选择当前方向的军用采购项目")
    case_ids = [case.id for case in cases]
    evidence = db.query(SupplyChainEvidence).filter(
        SupplyChainEvidence.case_id.in_(case_ids),
        SupplyChainEvidence.is_reportable == True,
    ).order_by(SupplyChainEvidence.score.desc()).all()
    if not evidence:
        raise HTTPException(400, "没有经过审核且可用于报告的证据链")
    model = db.get(ModelConfig, data.model_id) if data.model_id else get_default_model(db)
    if not model or not model.is_active:
        raise HTTPException(400, "请先配置并启用报告生成模型")

    evidence_rows = []
    for item in evidence:
        case = db.get(SupplyChainCase, item.case_id)
        shipment = db.get(SupplyChainShipment, item.shipment_id)
        evidence_rows.append({
            "evidence_id": item.id,
            "grade": item.evidence_grade,
            "case": _dump(case, CASE_FIELDS),
            "shipment": _dump(shipment, SHIPMENT_FIELDS),
            "reasoning": item.reasoning,
            "verified_facts": item.verified_facts,
            "limitations": (item.model_review or {}).get("limitations", []),
        })
    direction_name = COUNTRY_NAMES.get(data.country, data.country)
    investigation_name = investigation.name if investigation else f"{direction_name}全部供应链"
    title = data.title or f"{investigation_name}自华进口关联分析报告"
    prompt = f"""
请根据以下经审核证据，撰写一篇{direction_name}军工供应链穿透分析报告。
报告标题：{title}

写作要求：
1. 采用正式情报研究报告体例，包括基本情况、供应链证据链、综合研判、风险提示和后续核查方向。
2. 每项事实后标注[证据ID]；不得使用未提供的信息，不得虚构企业、合同、提单或最终用途。
3. A级可表述为直接证实；B级只能表述为高度关联或可能经加工后进入；C级只能列为风险线索。
4. 明确区分“已证实事实”“分析判断”“尚待核实”，不能用时间重合替代因果证明。
5. 保留企业真实名称供内部研判，报告语言使用中文，不使用多余装饰符号。
6. 结尾以===SEPARATOR===分隔，并给出200字以内报告摘要。

证据数据：
{json.dumps(evidence_rows, ensure_ascii=False, default=str)}
""".strip()
    report = SupplyChainReport(
        id=f"scr-{uuid4().hex[:12]}", country=data.country, title=title,
        case_ids=case_ids, evidence_ids=[item.id for item in evidence],
        model_id=model.id, status="generating",
    )
    db.add(report)
    _attach(db, data.investigation_id, "report_ids", report.id)
    db.commit()
    try:
        result = await call_llm(model, prompt, max_tokens_override=8000, timeout_seconds=300)
        report.content = result["content"]
        report.summary = result["summary"]
        report.status = "completed"
        report.generated_at = _now()
    except Exception as exc:
        report.status = "failed"
        report.error_log = str(exc)
    db.commit()
    db.refresh(report)
    return _dump(report, REPORT_FIELDS)
