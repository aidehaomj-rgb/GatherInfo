"""Persist normalized cases, entities and evidence relationships."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import urlparse

from sqlalchemy.orm import Session

from app.models import CollectedItem, ResearchCase, ResearchCaseEntity, ResearchEntity, ResearchEvidence

ENTITY_MAP = {
    "companies": "company", "people": "person", "vessels": "vessel",
    "flights": "flight", "flight_numbers": "flight", "container_numbers": "container",
    "imo_numbers": "imo", "case_numbers": "case_number", "bill_numbers": "bill_number",
    "ports": "port", "goods": "goods", "identifiers": "identifier",
}


def sync_research_graph(db: Session, items: list[CollectedItem]) -> dict:
    cases = entities = relations = evidence = 0
    for item in items:
        review = (item.raw_metadata or {}).get("enforcement_review") or {}
        research = (item.raw_metadata or {}).get("entity_research") or {}
        case_id = "case-" + hashlib.sha1(item.id.encode()).hexdigest()[:16]
        case = db.get(ResearchCase, case_id)
        if not case:
            case = ResearchCase(id=case_id, topic_id=item.topic_id, primary_item_id=item.id, title=item.title)
            db.add(case); cases += 1
        case.jurisdiction = review.get("jurisdiction")
        case.china_relevance = review.get("china_relevance_level")
        case.verification_status = research.get("cross_source_status", "single_source")
        corroborating = research.get("corroborating_sources") or []
        case.source_count = 1 + len(corroborating)
        db.flush()

        source_rows = [{"item_id": item.id, "url": item.url, "quote": review.get("evidence_quote")}, *corroborating]
        for source in source_rows:
            url = str(source.get("url") or "").strip()
            if not url:
                continue
            ev_id = "ev-" + hashlib.sha1(f"{case_id}|{url}".encode()).hexdigest()[:20]
            if not db.get(ResearchEvidence, ev_id):
                db.add(ResearchEvidence(id=ev_id, case_id=case_id, item_id=source.get("item_id") or item.id,
                    url=url, domain=urlparse(url).netloc.casefold(), quote=source.get("quote"), is_independent=True)); evidence += 1

        entity_count = 0
        for key, entity_type in ENTITY_MAP.items():
            for value in (item.entities or {}).get(key) or []:
                canonical = _canonical(str(value))
                if not canonical:
                    continue
                entity_id = "ent-" + hashlib.sha1(f"{entity_type}|{canonical}".encode()).hexdigest()[:18]
                entity = db.get(ResearchEntity, entity_id)
                if not entity:
                    entity = ResearchEntity(id=entity_id, canonical_name=str(value).strip(), entity_type=entity_type,
                        aliases=[str(value).strip()], confidence=0.8)
                    db.add(entity); entities += 1
                    db.flush()
                relation_id = f"rel-{case_id[5:]}-{entity_id[4:]}"
                if not db.get(ResearchCaseEntity, relation_id):
                    db.add(ResearchCaseEntity(id=relation_id, case_id=case_id, entity_id=entity_id,
                        role=key, source_item_id=item.id, confidence=entity.confidence)); relations += 1
                entity_count += 1
        case.entity_count = entity_count
    db.flush()
    return {"cases_new": cases, "entities_new": entities, "relations_new": relations, "evidence_new": evidence}


def _canonical(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", value.casefold())
