from datetime import date

from app.research_planner import _enforcement_quota_queries


def test_enforcement_queries_are_china_nexus_dominant():
    queries = _enforcement_quota_queries(date(2026, 8, 13), 40)
    china = [query for query in queries if any(marker in query.casefold() for marker in ("china", "chinese", "中国", "中國"))]
    assert len(queries) == 40
    assert len(china) >= 28
