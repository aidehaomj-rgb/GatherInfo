"""US defence supply-chain penetration analysis routes."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.llm_client import call_llm
from app.model_defaults import get_default_model
from app.models import (
    ModelConfig,
    SupplyChainCase,
    SupplyChainEntity,
    SupplyChainEvidence,
    SupplyChainInvestigation,
    SupplyChainOpenSourceEvidence,
    SupplyChainReport,
    SupplyChainShipment,
)

router = APIRouter(prefix="/api/v1/supply-chain", tags=["supply-chain"])


def _now():
    return datetime.now(timezone.utc)


def _parse_date(value: str | None):
    if not value:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.replace(tzinfo=parsed.tzinfo or timezone.utc)


def _norm(value: str | None) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", (value or "").casefold())


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


@router.get("/investigations")
def list_investigations(country: str = "United States", db: Session = Depends(get_db)):
    _ensure_default_investigation(db)
    rows = db.query(SupplyChainInvestigation).filter(
        SupplyChainInvestigation.country == country
    ).order_by(SupplyChainInvestigation.created_at.asc()).all()
    return [_dump(row, INVESTIGATION_FIELDS) for row in rows]


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
    return _dump(row, INVESTIGATION_FIELDS)


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
    query = db.query(SupplyChainOpenSourceEvidence).join(
        SupplyChainCase, SupplyChainCase.id == SupplyChainOpenSourceEvidence.case_id
    ).filter(SupplyChainCase.country == country)
    investigation = _get_investigation(db, country, investigation_id)
    if investigation:
        query = query.filter(
            SupplyChainOpenSourceEvidence.id.in_(
                investigation.open_source_evidence_ids or []
            )
        )
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
