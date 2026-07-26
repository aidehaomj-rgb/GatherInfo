import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.research_planner import build_research_queries


def _topic(**overrides):
    values = {
        "id": "topic-risk",
        "name": "境外查发走私违规案件",
        "description": "关注境外海关查发且对中国海关风险防控有参考价值的案件。",
        "keywords": ["境外海关查获", "走私违规", "中国关联"],
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_keyword_topic_is_converted_to_semantic_queries_with_configured_window(monkeypatch):
    llm = AsyncMock(return_value={
        "content": '{"queries":["overseas customs seizure smuggling China-linked supply chain"]}',
    })
    monkeypatch.setattr("app.research_planner.call_llm", llm)

    queries = asyncio.run(build_research_queries(
        _topic(),
        "",
        SimpleNamespace(is_active=True, model_name="model"),
        max_queries=8,
        window_days=30,
        today=date(2026, 7, 26),
    ))

    assert queries == ["overseas customs seizure smuggling China-linked supply chain"]
    prompt = llm.await_args.args[1]
    assert "2026-06-26" in prompt
    assert "semantic intent" in prompt
    assert "Do not require every literal keyword" in prompt


def test_fallback_queries_remain_topic_specific_when_model_is_unavailable(monkeypatch):
    monkeypatch.setattr(
        "app.research_planner.call_llm",
        AsyncMock(side_effect=RuntimeError("offline")),
    )

    queries = asyncio.run(build_research_queries(
        _topic(name="关键矿产出口管制", keywords=["关键矿产", "出口管制"]),
        "",
        None,
        max_queries=4,
        window_days=14,
        today=date(2026, 7, 26),
    ))

    assert queries
    assert all("关键矿产出口管制" in query for query in queries)
    assert any("2026-07-12" in query for query in queries)
