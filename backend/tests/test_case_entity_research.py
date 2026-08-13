from types import SimpleNamespace

from app.case_entity_research import build_gap_followups, enrich_case_entities, update_cross_source_verification
from app.research_planner import _parse_followup_queries


def test_extract_transport_and_company_entities():
    item = SimpleNamespace(
        title="Customs case 24-CR-778",
        summary="ABC Logistics Ltd shipped container MSKU1234567.",
        content="The vessel IMO 9876543 carried B/L no. COSU-991122 from China.",
        entities={},
        raw_metadata={"enforcement_review": {"subject": "ABC Logistics Ltd", "jurisdiction": "Canada"}},
    )
    entities = enrich_case_entities(item)
    assert "MSKU1234567" in entities["container_numbers"]
    assert any("IMO" in value for value in entities["imo_numbers"])
    assert "ABC Logistics Ltd" in entities["companies"]
    assert item.raw_metadata["entity_research"]["status"] == "extracted"


def test_gap_followups_include_named_entities_and_china_gap():
    item = SimpleNamespace(
        title="Seizure involving Example Trading LLC",
        summary="Customs seized cargo.", content="", entities={},
        raw_metadata={"enforcement_review": {"subject": "Example Trading LLC", "jurisdiction": "Canada", "china_relevance_level": "major_non_china"}},
    )
    queries = build_gap_followups([item], window_start="2026-08-07", window_end="2026-08-13")
    assert any("Example Trading LLC" in query for query in queries)
    assert any('"from China"' in query for query in queries)


def test_followup_query_marker_parses_json():
    prompt = 'round two\n[FOLLOWUP_QUERIES] ["company customs", "MSKU1234567"]'
    assert _parse_followup_queries(prompt) == ["company customs", "MSKU1234567"]


def test_cross_source_verification_requires_independent_domain():
    first = SimpleNamespace(id="a", title="Case", content="Container MSKU1234567", url="https://one.example/case", entities={"container_numbers": ["MSKU1234567"]}, raw_metadata={})
    same = SimpleNamespace(id="b", title="Copy", content="", url="https://one.example/copy", entities={"container_numbers": ["MSKU1234567"]}, raw_metadata={})
    other = SimpleNamespace(id="c", title="Court", content="", url="https://two.example/court", entities={"container_numbers": ["MSKU1234567"]}, raw_metadata={})
    update_cross_source_verification([first, same])
    assert first.raw_metadata["entity_research"]["cross_source_status"] == "single_source"
    update_cross_source_verification([first, same, other])
    assert first.raw_metadata["entity_research"]["cross_source_status"] == "verified"
