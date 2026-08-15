"""Export reviewable application configuration without local credentials."""
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy import MetaData, Table, select  # noqa: E402

from app.database import engine, SessionLocal  # noqa: E402
from app.models import (  # noqa: E402
    Category,
    PromptTemplate,
    SearchToolConfig,
    SourceConfig,
    SupplyChainCase,
    SupplyChainDiscoveryCandidate,
    SupplyChainEntity,
    SupplyChainEvidence,
    SupplyChainInvestigation,
    SupplyChainOpenSourceEvidence,
    SupplyChainReport,
    SupplyChainShipment,
    Topic,
)

OUTPUT_DIR = ROOT / "config" / "snapshots"
SECRET_NAMES = {
    "api_key",
    "access_token",
    "authorization",
    "client_secret",
    "credential",
    "credentials",
    "password",
    "secret",
    "token",
}

CATEGORY_FIELDS = ("id", "name", "description")
SOURCE_FIELDS = (
    "id", "name", "description", "channel", "source_group", "is_active",
    "is_configured", "base_url", "api_endpoint", "homepage_url", "api_key_ref",
    "auth_config", "rate_limit_rps", "max_retries", "timeout_seconds",
    "max_items_per_run", "default_keywords", "default_categories", "languages",
    "country_focus", "legal_basis", "compliance_note",
)
PROMPT_FIELDS = ("id", "name", "description", "content", "is_active")
TOPIC_FIELDS = (
    "id", "name", "description", "is_active", "category_id", "keywords",
    "synonyms", "exclude_keywords", "categories", "focus_countries",
    "focus_languages", "target_urls", "is_scheduled", "keyword_tags",
    "auto_tag_rules", "source_ids", "collection_model_ids", "prompt_template_ids",
    "schedule_cron", "collect_window_days", "auto_report", "auto_report_model_id",
    "auto_report_type", "description_prompt", "ai_research_model_id",
)
TOOL_FIELDS = (
    "id", "name", "tool_type", "is_active", "config_json", "api_key_ref",
    "is_default",
)
SUPPLY_CHAIN_MODELS = {
    "investigations": (SupplyChainInvestigation, (
        "id", "country", "name", "description", "status", "entity_ids",
        "case_ids", "shipment_ids", "evidence_ids", "open_source_evidence_ids",
        "report_ids",
    )),
    "entities": (SupplyChainEntity, (
        "id", "name", "name_zh", "country", "entity_type", "aliases",
        "parent_id", "defense_roles", "source_url", "notes",
    )),
    "cases": (SupplyChainCase, (
        "id", "country", "title", "procurement_agency", "procurement_reference",
        "procurement_date", "supplier_entity_id", "product", "target_program",
        "contract_value", "currency", "source_url", "source_excerpt", "status",
    )),
    "shipments": (SupplyChainShipment, (
        "id", "exporter_name", "exporter_country", "importer_entity_id",
        "importer_name", "product", "hs_code", "shipment_date", "weight_kg",
        "quantity", "quantity_unit", "origin_country", "destination_country",
        "bill_no", "source_name", "source_url", "raw_record",
    )),
    "evidence": (SupplyChainEvidence, (
        "id", "case_id", "shipment_id", "relation_type", "evidence_grade",
        "score", "status", "reasoning", "verified_facts", "model_review",
        "is_reportable",
    )),
    "open_source_evidence": (SupplyChainOpenSourceEvidence, (
        "id", "case_id", "title", "source_type", "source_publisher",
        "source_url", "source_excerpt", "verified_facts", "evidence_grade",
        "status", "limitations",
    )),
    "reports": (SupplyChainReport, (
        "id", "country", "title", "case_ids", "evidence_ids", "model_id",
        "status", "content", "summary", "error_log", "generated_at",
    )),
    "discovery_candidates": (SupplyChainDiscoveryCandidate, (
        "id", "country", "case_id", "shipment_id", "supplier_entity_id",
        "title", "target_program", "exporter_name", "importer_name", "product",
        "score", "evidence_grade", "verified_facts", "status", "review_note",
        "investigation_id", "reviewed_at",
    )),
}
CONTENT_TABLES = (
    "collected_items",
    "reports",
    "tags",
    "item_tags",
    "research_jobs",
    "research_rounds",
    "research_cases",
    "research_case_entities",
    "research_entities",
    "research_evidence",
)


def _is_secret_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in SECRET_NAMES or normalized.endswith("_secret") or normalized.endswith("_token")


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            str(key): "${REDACTED}" if _is_secret_key(str(key)) and item else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def serialize_rows(rows: list[Any], fields: tuple[str, ...]) -> list[dict[str, Any]]:
    return [
        sanitize({field: getattr(row, field) for field in fields})
        for row in sorted(rows, key=lambda item: item.id)
    ]


def write_snapshot(filename: str, rows: list[Any], fields: tuple[str, ...]) -> None:
    payload = serialize_rows(rows, fields)
    path = OUTPUT_DIR / filename
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{filename}: {len(payload)}")


def write_supply_chain_snapshot(db: Any) -> None:
    payload = {
        name: serialize_rows(db.query(model).all(), fields)
        for name, (model, fields) in SUPPLY_CHAIN_MODELS.items()
    }
    path = OUTPUT_DIR / "supply_chain.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = ", ".join(f"{name}={len(rows)}" for name, rows in payload.items())
    print(f"supply_chain.json: {counts}")


def write_content_archive(db: Any) -> None:
    metadata = MetaData()
    payload: dict[str, list[dict[str, Any]]] = {}
    for table_name in CONTENT_TABLES:
        table = Table(table_name, metadata, autoload_with=engine)
        order_columns = list(table.primary_key.columns) or list(table.columns)[:1]
        rows = db.execute(select(table).order_by(*order_columns)).mappings().all()
        payload[table_name] = [sanitize(dict(row)) for row in rows]
    path = OUTPUT_DIR / "content_archive.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    counts = ", ".join(f"{name}={len(rows)}" for name, rows in payload.items())
    print(f"content_archive.json: {counts}")


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with SessionLocal() as db:
        write_snapshot("collection_categories.json", db.query(Category).all(), CATEGORY_FIELDS)
        write_snapshot("information_sources.json", db.query(SourceConfig).all(), SOURCE_FIELDS)
        write_snapshot("prompt_templates.json", db.query(PromptTemplate).all(), PROMPT_FIELDS)
        write_snapshot("topics.json", db.query(Topic).all(), TOPIC_FIELDS)
        write_snapshot("mcp_tools.json", db.query(SearchToolConfig).all(), TOOL_FIELDS)
        write_supply_chain_snapshot(db)
        write_content_archive(db)


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
