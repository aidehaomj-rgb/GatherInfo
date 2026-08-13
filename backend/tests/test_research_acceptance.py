from types import SimpleNamespace

from app.research_acceptance import acceptance_followups, evaluate_acceptance


def _item(*, china="strong", jurisdiction="Canada", verified=True, official=True, entities=True):
    return SimpleNamespace(
        title="Case", summary="", language="zh", url=("https://cbsa.gc.ca/case" if official else "https://news.example/case"),
        entities={"companies": ["Example Ltd"]} if entities else {},
        raw_metadata={"enforcement_review": {"china_relevance_level": china, "jurisdiction": jurisdiction},
                      "entity_research": {"cross_source_status": "verified" if verified else "single_source"}},
    )


def test_acceptance_passes_balanced_portfolio():
    rows = [_item(jurisdiction=value) for value in ("Canada", "Australia", "Japan", "India", "Brazil")]
    result = evaluate_acceptance(rows, {"min_items": 5, "min_official_rate": 0})
    assert result["passed"] is True


def test_acceptance_returns_targeted_followups():
    result = evaluate_acceptance([_item(china="major_non_china", verified=False, entities=False, official=False)], {"min_items": 5})
    queries = acceptance_followups(result, "2026-08-07", "2026-08-13")
    assert "china_ratio" in result["gaps"]
    assert any("from China" in query for query in queries)
    assert any("court indictment" in query for query in queries)
