"""Structured models for defence supply-chain investigations."""
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Text

from app.database import Base


def _utc_now():
    return datetime.now(timezone.utc)


class SupplyChainInvestigation(Base):
    __tablename__ = "supply_chain_investigations"

    id = Column(String(80), primary_key=True)
    country = Column(String(80), nullable=False, index=True)
    name = Column(String(300), nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="active")
    entity_ids = Column(JSON, nullable=True)
    case_ids = Column(JSON, nullable=True)
    shipment_ids = Column(JSON, nullable=True)
    evidence_ids = Column(JSON, nullable=True)
    open_source_evidence_ids = Column(JSON, nullable=True)
    report_ids = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)


class SupplyChainEntity(Base):
    __tablename__ = "supply_chain_entities"

    id = Column(String(80), primary_key=True)
    name = Column(String(300), nullable=False, index=True)
    name_zh = Column(String(300), nullable=True)
    country = Column(String(80), nullable=False, default="United States")
    entity_type = Column(String(50), nullable=False, default="defense_supplier")
    aliases = Column(JSON, nullable=True)
    parent_id = Column(String(80), ForeignKey("supply_chain_entities.id"), nullable=True)
    defense_roles = Column(JSON, nullable=True)
    source_url = Column(String(1000), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)


class SupplyChainCase(Base):
    __tablename__ = "supply_chain_cases"

    id = Column(String(80), primary_key=True)
    country = Column(String(80), nullable=False, default="United States", index=True)
    title = Column(String(500), nullable=False)
    procurement_agency = Column(String(300), nullable=True)
    procurement_reference = Column(String(200), nullable=True)
    procurement_date = Column(DateTime(timezone=True), nullable=True)
    supplier_entity_id = Column(
        String(80), ForeignKey("supply_chain_entities.id"), nullable=True, index=True
    )
    product = Column(String(500), nullable=True)
    target_program = Column(String(500), nullable=True)
    contract_value = Column(Float, nullable=True)
    currency = Column(String(20), nullable=True, default="USD")
    source_url = Column(String(1000), nullable=True)
    source_excerpt = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="monitoring")
    created_at = Column(DateTime(timezone=True), default=_utc_now)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)


class SupplyChainShipment(Base):
    __tablename__ = "supply_chain_shipments"

    id = Column(String(80), primary_key=True)
    exporter_name = Column(String(300), nullable=False)
    exporter_country = Column(String(80), nullable=True, default="China")
    importer_entity_id = Column(
        String(80), ForeignKey("supply_chain_entities.id"), nullable=True, index=True
    )
    importer_name = Column(String(300), nullable=False)
    product = Column(String(500), nullable=False)
    hs_code = Column(String(30), nullable=True)
    shipment_date = Column(DateTime(timezone=True), nullable=True, index=True)
    weight_kg = Column(Float, nullable=True)
    quantity = Column(Float, nullable=True)
    quantity_unit = Column(String(50), nullable=True)
    origin_country = Column(String(80), nullable=True, default="China")
    destination_country = Column(String(80), nullable=True, default="United States")
    bill_no = Column(String(150), nullable=True)
    source_name = Column(String(200), nullable=True)
    source_url = Column(String(1000), nullable=True)
    raw_record = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now)


class SupplyChainEvidence(Base):
    __tablename__ = "supply_chain_evidence"

    id = Column(String(80), primary_key=True)
    case_id = Column(String(80), ForeignKey("supply_chain_cases.id"), nullable=False, index=True)
    shipment_id = Column(
        String(80), ForeignKey("supply_chain_shipments.id"), nullable=False, index=True
    )
    relation_type = Column(String(50), nullable=False, default="possible_supply")
    evidence_grade = Column(String(10), nullable=False, default="C")
    score = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="pending")
    reasoning = Column(Text, nullable=True)
    verified_facts = Column(JSON, nullable=True)
    model_review = Column(JSON, nullable=True)
    is_reportable = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), default=_utc_now)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)


class SupplyChainOpenSourceEvidence(Base):
    __tablename__ = "supply_chain_open_source_evidence"

    id = Column(String(80), primary_key=True)
    case_id = Column(String(80), ForeignKey("supply_chain_cases.id"), nullable=True, index=True)
    title = Column(String(500), nullable=False)
    source_type = Column(String(80), nullable=False, default="official_document")
    source_publisher = Column(String(300), nullable=True)
    source_url = Column(String(1000), nullable=False)
    source_excerpt = Column(Text, nullable=True)
    verified_facts = Column(JSON, nullable=True)
    evidence_grade = Column(String(10), nullable=False, default="C")
    status = Column(String(30), nullable=False, default="verified")
    limitations = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now)
    updated_at = Column(DateTime(timezone=True), default=_utc_now, onupdate=_utc_now)


class SupplyChainReport(Base):
    __tablename__ = "supply_chain_reports"

    id = Column(String(80), primary_key=True)
    country = Column(String(80), nullable=False, default="United States")
    title = Column(String(500), nullable=False)
    case_ids = Column(JSON, nullable=True)
    evidence_ids = Column(JSON, nullable=True)
    model_id = Column(String(80), nullable=True)
    status = Column(String(30), nullable=False, default="pending")
    content = Column(Text, nullable=True)
    summary = Column(Text, nullable=True)
    error_log = Column(Text, nullable=True)
    generated_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utc_now)
