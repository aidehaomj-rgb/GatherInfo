from datetime import datetime, timezone
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.models import SupplyChainCase, SupplyChainEntity, SupplyChainShipment
from app.routes.supply_chain import _build_discovery_candidates, _chain_signature_matches
from app.supply_chain_online import (
    _attach_deterministic_contract_evidence,
    _deep_china_trade_queries,
    _entity_display_name,
    _extract_structured_trade_records,
    _merge_candidate_evidence,
    _queries,
    _signal_sets,
    qualify_candidates,
)
from app.supply_chain_trade_records import build_public_trade_index_probes


def test_supply_chain_expert_finds_related_china_import() -> None:
    supplier = SupplyChainEntity(
        id="entity-acme",
        name="Acme Defense",
        country="United States",
        aliases=["Acme Defense Systems"],
    )
    case = SupplyChainCase(
        id="case-radar",
        country="United States",
        title="Radar module contract",
        supplier_entity_id=supplier.id,
        product="radar module PN-12345",
        target_program="Air-defense radar",
        procurement_reference="W91-2026-C-001",
        source_url="https://official.example/contract.pdf",
        source_excerpt="Acme will deliver PN-12345 radar modules.",
        procurement_date=datetime(2026, 1, 15, tzinfo=timezone.utc),
    )
    shipment = SupplyChainShipment(
        id="shipment-radar",
        exporter_name="Shenzhen Components",
        exporter_country="China",
        importer_entity_id=supplier.id,
        importer_name="Acme Defense Systems",
        product="radar module housing PN-12345",
        origin_country="China",
        destination_country="United States",
        shipment_date=datetime(2026, 1, 8, tzinfo=timezone.utc),
        bill_no="BOL-2026-001",
        source_url="https://trade.example/record/BOL-2026-001",
    )

    candidates = _build_discovery_candidates(
        cases=[case],
        shipments=[shipment],
        entities=[supplier],
        minimum_score=60,
    )

    assert len(candidates) == 1
    assert candidates[0]["case_id"] == case.id
    assert candidates[0]["shipment_id"] == shipment.id
    assert candidates[0]["score"] == 100
    assert candidates[0]["evidence_grade"] == "A"
    assert candidates[0]["verified_facts"]["mcp_checks"]["part_number_match"] is True


def test_supply_chain_expert_caps_score_without_primary_evidence() -> None:
    supplier = SupplyChainEntity(id="entity-acme", name="Acme Defense")
    case = SupplyChainCase(
        id="case-radar", country="United States", title="Radar contract",
        supplier_entity_id=supplier.id, product="radar module",
    )
    shipment = SupplyChainShipment(
        id="shipment-radar", exporter_name="China Parts", exporter_country="China",
        importer_entity_id=supplier.id, importer_name="Acme Defense",
        product="radar module", origin_country="China",
        destination_country="United States",
    )

    candidates = _build_discovery_candidates(
        cases=[case], shipments=[shipment], entities=[supplier], minimum_score=0,
    )

    assert candidates[0]["score"] == 74
    assert candidates[0]["evidence_grade"] == "B"


def test_supply_chain_expert_rejects_non_china_origin() -> None:
    supplier = SupplyChainEntity(id="entity-acme", name="Acme Defense")
    case = SupplyChainCase(
        id="case-radar",
        country="United States",
        title="Radar contract",
        supplier_entity_id=supplier.id,
        product="radar",
    )
    shipment = SupplyChainShipment(
        id="shipment-radar",
        exporter_name="EU Components",
        exporter_country="Germany",
        importer_entity_id=supplier.id,
        importer_name="Acme Defense",
        product="radar",
        origin_country="Germany",
        destination_country="United States",
    )

    assert _build_discovery_candidates(
        cases=[case], shipments=[shipment], entities=[supplier], minimum_score=0,
    ) == []


def test_online_candidate_requires_two_real_search_urls() -> None:
    contract_url = "https://official.example/contracts/award.pdf"
    trade_url = "https://trade.example/shipments/123"
    content = """[{"country":"United States","importer_name":"Acme Defense",
    "exporter_name":"Shenzhen Parts","product":"radar module",
    "contract_title":"Acme radar award","contract_evidence_url":"%s",
    "trade_evidence_url":"%s","supporting_urls":[],"confidence_score":88}]""" % (contract_url, trade_url)

    rows = qualify_candidates(content, {contract_url, trade_url}, {"United States"})

    assert len(rows) == 1
    assert rows[0]["contract_evidence_url"] == contract_url


def test_online_candidate_rejects_fabricated_or_single_source_url() -> None:
    allowed = "https://official.example/contracts/award.pdf"
    content = """[{"country":"United States","importer_name":"Acme Defense",
    "exporter_name":"Shenzhen Parts","product":"radar module",
    "contract_title":"Acme radar award","contract_evidence_url":"%s",
    "trade_evidence_url":"https://invented.example/trade","confidence_score":90}]""" % allowed

    assert qualify_candidates(content, {allowed}, {"United States"}) == []


def test_online_candidate_keeps_single_source_as_partial_lead() -> None:
    allowed = "https://official.example/contracts/award.pdf"
    content = """[{"country":"United States","importer_name":"Acme Defense",
    "exporter_name":"Shenzhen Parts","product":"radar module",
    "contract_title":"Acme radar award","contract_evidence_url":"%s",
    "trade_evidence_url":null,"confidence_score":65}]""" % allowed

    rows = qualify_candidates(
        content, {allowed}, {"United States"}, allow_partial=True,
    )

    assert len(rows) == 1
    assert rows[0]["evidence_status"] == "contract_only"
    assert rows[0]["trade_evidence_url"] is None
    assert "中国进口记录" in rows[0]["evidence_gap"]


def test_contract_only_lead_can_wait_for_exporter_identification() -> None:
    allowed = "https://official.example/contracts/award.pdf"
    content = """[{"country":"United States","importer_name":"Acme Defense",
    "exporter_name":null,"product":"radar module",
    "contract_title":"Acme radar award","contract_evidence_url":"%s",
    "trade_evidence_url":null,"confidence_score":62}]""" % allowed

    rows = qualify_candidates(
        content, {allowed}, {"United States"}, allow_partial=True,
    )

    assert rows[0]["exporter_name"] == "待识别中国供应商"


def test_search_results_are_split_into_trade_and_military_signal_sets() -> None:
    signals = _signal_sets([
        {"title": "2026 bill of lading", "summary": "Imports from China", "url": "https://trade.example"},
        {"title": "Army contract award", "summary": "Defense procurement", "url": "https://official.example"},
    ])

    assert len(signals["china_trade_signals"]) == 1
    assert len(signals["military_use_signals"]) == 1


def test_deep_trade_queries_target_2026_and_trade_indexes() -> None:
    queries = _deep_china_trade_queries("United States")

    assert any("2026" in query and "bill of lading" in query for query in queries)
    assert any("site:importyeti.com" in query for query in queries)
    assert any("site:panjiva.com" in query for query in queries)


def test_existing_bilingual_chain_signature_is_detected() -> None:
    assert _chain_signature_matches(
        "Teledyne FLIR", "Mobile Surveillance Systems",
        "泰莱达·菲力尔（Teledyne FLIR）", "mobile surveillance systems",
    )
    assert not _chain_signature_matches(
        "Teledyne FLIR", "Mobile Surveillance Systems",
        "AeroVironment", "counter-drone system",
    )


def test_online_trade_edge_requires_recent_supported_date() -> None:
    contract_url = "https://sam.gov/opp/ultralife"
    trade_url = "https://www.importgenius.com/importers/ultralife-corporation"
    content = """[{"country":"United States","importer_name":"Ultralife Corporation",
    "exporter_name":"Tianjin Lishen Battery Joint-Stock","product":"锂离子电芯",
    "contract_title":"军用电池合同","contracting_agency":"U.S. Army",
    "contract_evidence_url":"%s","trade_evidence_url":"%s",
    "trade_date":"2026-08-12","trade_date_basis":"shipment_record",
    "trade_excerpt":"Arrival Date 2026-08-12; China; lithium ion cell",
    "confidence_score":88}]""" % (contract_url, trade_url)
    sources = [
        {"url": contract_url, "title": "Ultralife Army contract award", "summary": "Defense battery procurement for Ultralife Corporation"},
        {"url": trade_url, "title": "Ultralife Corporation importer records", "content": "US Customs shipments from Tianjin Lishen Battery Joint-Stock, a supplier based in China, to Ultralife Corporation. Arrival Date 2026-08-12."},
    ]

    rows = qualify_candidates(
        content, {contract_url, trade_url}, {"United States"}, allow_partial=True,
        source_records=sources, import_record_window_days=365,
        as_of=datetime(2026, 8, 15, tzinfo=timezone.utc),
    )

    assert rows[0]["evidence_status"] == "closed"
    assert rows[0]["trade_date"] == "2026-08-12"
    assert rows[0]["evidence_validation"]["trade"]["valid"] is True


def test_old_trade_record_is_demoted_but_old_contract_is_allowed() -> None:
    contract_url = "https://sam.gov/opp/ultralife"
    trade_url = "https://www.importgenius.com/importers/ultralife-corporation"
    content = """[{"country":"United States","importer_name":"Ultralife Corporation",
    "exporter_name":"Tianjin Lishen Battery Joint-Stock","product":"锂离子电芯",
    "contract_title":"2021年军用电池合同","contracting_agency":"U.S. Army",
    "contract_date":"2021-05-01","contract_evidence_url":"%s",
    "trade_evidence_url":"%s","trade_date":"2025-01-10",
    "trade_excerpt":"Arrival Date 2025-01-10; supplier based in China",
    "confidence_score":82}]""" % (contract_url, trade_url)
    sources = [
        {"url": contract_url, "title": "Ultralife Army contract award", "summary": "2021 defense contract for Ultralife Corporation"},
        {"url": trade_url, "title": "Ultralife Corporation importer records", "content": "Ultralife Corporation imports from China. Arrival Date 2025-01-10."},
    ]

    rows = qualify_candidates(
        content, {contract_url, trade_url}, {"United States"}, allow_partial=True,
        source_records=sources, import_record_window_days=365,
        as_of=datetime(2026, 8, 15, tzinfo=timezone.utc),
    )

    assert rows[0]["evidence_status"] == "contract_only"
    assert rows[0]["contract_date"] == "2021-05-01"
    assert rows[0]["trade_evidence_url"] is None
    assert "超出时间范围" in rows[0]["evidence_gap"]


def test_procurement_agency_cannot_be_used_as_target_importer() -> None:
    url = "https://sam.gov/opp/mobile-surveillance"
    content = """[{"country":"United States",
    "importer_name":"U.S. Customs and Border Protection","product":"监控系统",
    "contract_title":"移动监控合同","contracting_agency":"U.S. Customs and Border Protection",
    "contract_evidence_url":"%s","trade_evidence_url":null,"confidence_score":70}]""" % url

    assert qualify_candidates(
        content, {url}, {"United States"}, allow_partial=True,
        source_records=[{"url": url, "title": "CBP defense procurement", "summary": "Contract award"}],
        import_record_window_days=365,
        as_of=datetime(2026, 8, 15, tzinfo=timezone.utc),
    ) == []


def test_country_queries_include_real_multilingual_searches() -> None:
    as_of = datetime(2026, 8, 15, tzinfo=timezone.utc)
    japan = _queries("Japan", as_of=as_of)
    india = _queries("India", as_of=as_of)
    taiwan = _queries("Taiwan", as_of=as_of)

    assert any(query.startswith("ja-JP||") and "中国から輸入" in query for query in japan)
    assert any(query.startswith("hi-IN||") and "चीन से आयात" in query for query in india)
    assert any(query.startswith("zh-TW||") and "中國進口" in query for query in taiwan)


def test_importgenius_table_is_extracted_without_model_guessing() -> None:
    source_url = "https://www.importgenius.com/importers/ultralife-corporation"
    source = {
        "url": source_url,
        "title": "Ultralife Corporation | See Full Importer History | ImportGenius",
        "country_hint": "United States",
        "content": """
Importer Shipments
#
Bill of Lading
Product
Importer
Supplier
Arrival Date
Country of Origin
1
QEMLSHGS03286668
LITHIUM ION CELL
ULTRALIFE CORPORATION
TIANJIN LISHEN BATTERY JOINT STOCK
2026-08-12
China
1094 Kgs
112 CTN
2
OLD0000001
BATTERY
ULTRALIFE CORPORATION
OLD CHINA SUPPLIER
2024-01-02
China
100 Kgs
10 CTN
""",
    }

    rows = _extract_structured_trade_records(
        [source], ["United States"],
        as_of=datetime(2026, 8, 15, tzinfo=timezone.utc),
        import_record_window_days=365,
    )

    assert len(rows) == 1
    assert rows[0]["importer_name"] == "ULTRALIFE CORPORATION"
    assert rows[0]["exporter_name"] == "TIANJIN LISHEN BATTERY JOINT STOCK"
    assert rows[0]["trade_reference"] == "QEMLSHGS03286668"
    assert rows[0]["trade_date"] == "2026-08-12"
    assert rows[0]["trade_evidence_url"] == source_url
    assert rows[0]["deterministic_extraction"] is True


def test_public_trade_index_probes_are_built_from_discovered_importers() -> None:
    targets = [
        {
            "country": "United States",
            "company_name": "Acme Defense Systems, Inc.",
            "role": "defense_importer",
        },
        {
            "country": "United States",
            "company_name": "ACME DEFENSE SYSTEMS INC",
            "role": "defense_importer",
        },
        {
            "country": "United States",
            "company_name": "Shenzhen Parts Co., Ltd.",
            "role": "china_exporter",
        },
    ]

    probes = build_public_trade_index_probes(
        ["United States"], targets, max_probes=8,
    )

    assert probes == [(
        "United States",
        "Acme Defense Systems, Inc.",
        "acme-defense-systems-inc",
    )]


def test_deterministic_trade_record_closes_matching_contract_lead() -> None:
    contract_url = "https://investor.ultralifecorporation.com/news/army-contract"
    trade_url = "https://www.importgenius.com/importers/ultralife-corporation"
    contract_lead = {
        "country": "United States",
        "importer_name": "Ultralife Corporation",
        "exporter_name": "待识别中国供应商",
        "product": "军用电池",
        "contract_title": "美国陆军可穿戴电池合同",
        "contract_evidence_url": contract_url,
        "trade_evidence_url": None,
        "confidence_score": 70,
        "evidence_status": "contract_only",
        "evidence_gap": "待补近一年中国进口记录",
        "evidence_validation": {"contract": {"valid": True}, "trade": {"valid": False}},
        "supporting_urls": [],
        "limitations": [],
    }
    trade_lead = {
        "country": "United States",
        "importer_name": "ULTRALIFE CORPORATION",
        "exporter_name": "TIANJIN LISHEN BATTERY JOINT STOCK",
        "product": "LITHIUM ION CELL",
        "contract_title": "待核实国防合同或项目",
        "contract_evidence_url": None,
        "trade_evidence_url": trade_url,
        "trade_reference": "QEMLSHGS03286668",
        "trade_date": "2026-08-12",
        "trade_date_basis": "shipment_record",
        "trade_excerpt": "Arrival Date 2026-08-12; Country of Origin China",
        "confidence_score": 72,
        "evidence_status": "trade_only",
        "evidence_gap": "待补军工合同",
        "evidence_validation": {"contract": {"valid": False}, "trade": {"valid": True}},
        "supporting_urls": [],
        "limitations": [],
    }

    rows = _merge_candidate_evidence([contract_lead], [trade_lead], limit=5)

    assert len(rows) == 1
    assert rows[0]["evidence_status"] == "closed"
    assert rows[0]["contract_evidence_url"] == contract_url
    assert rows[0]["trade_evidence_url"] == trade_url
    assert rows[0]["exporter_name"] == "TIANJIN LISHEN BATTERY JOINT STOCK"
    assert rows[0]["product"] == "LITHIUM ION CELL"
    assert rows[0]["evidence_gap"] == ""
    assert any("具体批次" in item for item in rows[0]["limitations"])


def test_matching_battery_contract_is_attached_to_structured_trade_record() -> None:
    trade_url = "https://www.importgenius.com/importers/ultralife-corporation"
    contract_url = "https://investor.ultralifecorporation.com/news/army-battery-contract"
    trade_record = {
        "country": "United States",
        "importer_name": "ULTRALIFE CORPORATION",
        "exporter_name": "TIANJIN LISHEN BATTERY JOINT STOCK",
        "product": "LITHIUM ION CELL",
        "contract_title": None,
        "contract_evidence_url": None,
        "trade_evidence_url": trade_url,
        "trade_date": "2026-08-12",
        "confidence_score": 72,
        "limitations": [],
    }
    sources = [{
        "url": contract_url,
        "title": "Ultralife Corporation Awarded U.S. Army Battery Contract",
        "summary": (
            "Ultralife Corporation received an IDIQ contract from the U.S. Army "
            "for lithium-ion Conformal Wearable Batteries."
        ),
        "published_at": "2021-05-17T00:00:00+00:00",
    }]

    rows = _attach_deterministic_contract_evidence([trade_record], sources)

    assert rows[0]["contract_evidence_url"] == contract_url
    assert rows[0]["contract_title"] == sources[0]["title"]
    assert rows[0]["contract_date"] == "2021-05-17"
    assert rows[0]["confidence_score"] >= 80


def test_unrelated_defense_contract_does_not_close_trade_edge() -> None:
    trade_record = {
        "country": "United States",
        "importer_name": "GENERAL DYNAMICS",
        "exporter_name": "CHINA CONTAINER SUPPLIER",
        "product": "EMPTY METAL CONTAINER",
        "contract_evidence_url": None,
        "trade_evidence_url": "https://www.importgenius.com/importers/general-dynamics",
        "limitations": [],
    }
    sources = [{
        "url": "https://defense.example/general-dynamics-submarine-award",
        "title": "General Dynamics receives Navy submarine contract award",
        "summary": "The U.S. Navy awarded General Dynamics a contract for nuclear submarines.",
    }]

    rows = _attach_deterministic_contract_evidence([trade_record], sources)

    assert rows[0].get("contract_evidence_url") is None


def test_entity_display_name_does_not_repeat_untranslated_english_name() -> None:
    original = "ULTRALIFE CORPORATION"

    assert _entity_display_name(
        original, "ULTRALIFE CORPORATION (ULTRALIFE CORPORATION)",
    ) == original
    assert _entity_display_name(original, "奥特莱夫公司") == (
        "奥特莱夫公司（ULTRALIFE CORPORATION）"
    )
