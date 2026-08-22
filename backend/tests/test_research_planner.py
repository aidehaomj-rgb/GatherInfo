import asyncio
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.research_planner import build_research_queries
from app.topic_research_context import build_topic_research_context


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


def test_customs_hotspot_topic_uses_stable_risk_mission_matrix(monkeypatch):
    monkeypatch.setattr(
        "app.research_planner.call_llm",
        AsyncMock(side_effect=RuntimeError("offline")),
    )

    queries = asyncio.run(build_research_queries(
        _topic(id="weekly-trade-current-affairs", name="涉进出口时政热点"),
        "",
        None,
        max_queries=12,
        window_days=20,
        today=date(2026, 8, 4),
    ))

    assert len(queries) == 12
    assert all("2026-07-15" in query and "2026-08-04" in query for query in queries)
    assert any("China Russia border" in query for query in queries)
    assert any("cargo bound for China" in query for query in queries)
    assert any("fuel shortage" in query and "smuggling" in query for query in queries)
    assert any("fertilizer sulfur ammonia" in query and "China import route" in query for query in queries)
    assert any("dual use drone rare earth" in query and "third country procurement" in query for query in queries)
def test_weekly_global_topic_reserves_multilingual_search_lanes(monkeypatch):
    monkeypatch.setattr(
        "app.research_planner.call_llm",
        AsyncMock(return_value={
            "content": '{"queries":["official tariff update", "customs trade remedy news"]}',
        }),
    )
    topic = _topic(
        id="global-trade", name="全球贸易政策",
        weekly_digest_enabled=True,
    )

    queries = asyncio.run(build_research_queries(
        topic, "", SimpleNamespace(is_active=True, model_name="model"),
        max_queries=12, window_days=7, today=date(2026, 8, 4),
    ))

    assert len(queries) == 8
    assert queries[:2] == ["official tariff update", "customs trade remedy news"]
    assert any("aduanas" in query for query in queries)
    assert any("aduana" in query for query in queries)
    assert any("douanes" in query for query in queries)
    assert any("税関" in query for query in queries)
    assert any("관세청" in query for query in queries)


def test_exact_backfill_dates_override_rolling_window_hint(monkeypatch):
    llm = AsyncMock(return_value={"content": '{"queries":["official customs update"]}'})
    monkeypatch.setattr("app.research_planner.call_llm", llm)

    queries = asyncio.run(build_research_queries(
        _topic(), "", SimpleNamespace(is_active=True, model_name="model"),
        window_days=30, today=date(2026, 8, 4),
        window_start_date=date(2026, 7, 27),
        window_end_date=date(2026, 8, 2),
    ))

    prompt = llm.await_args.args[1]
    assert "2026-07-27 through 2026-08-02" in prompt
    assert "2026-07-05" not in prompt


def test_planner_uses_context_synonyms_exclusions_targets_and_focus_lanes(monkeypatch):
    llm = AsyncMock(return_value={"content": '{"queries":["official tariff notice"]}'})
    monkeypatch.setattr("app.research_planner.call_llm", llm)
    topic = _topic(
        id="global-trade", name="关税类贸易政策",
        synonyms=["customs duty"], exclude_keywords=["招聘"],
        focus_countries=["US"], focus_languages=["en"],
        target_urls=["https://ustr.gov"], categories=["tariff"],
        description_prompt="区分提议、公布与生效阶段",
    )
    context = build_topic_research_context(topic)

    queries = asyncio.run(build_research_queries(
        topic, "", SimpleNamespace(is_active=True, model_name="model"),
        max_queries=8, today=date(2026, 8, 17), research_context=context,
    ))

    prompt = llm.await_args.args[1]
    assert "customs duty" in prompt
    assert "招聘" in prompt
    assert "US" in prompt and "en" in prompt
    assert "https://ustr.gov" in prompt
    assert "区分提议、公布与生效阶段" in prompt
    assert any('-"招聘"' in query for query in queries)
    assert any("US" in query and "en" in query for query in queries)
    assert any("site:ustr.gov" in query for query in queries)


def test_second_round_fallback_targets_declared_gaps(monkeypatch):
    monkeypatch.setattr(
        "app.research_planner.call_llm",
        AsyncMock(side_effect=RuntimeError("offline")),
    )
    topic = _topic(
        id="global-trade", name="关税类贸易政策",
        synonyms=[], exclude_keywords=[], categories=["tariff"],
        focus_countries=["BR"], focus_languages=["pt"], target_urls=[],
        description_prompt="区分政策阶段",
    )

    queries = asyncio.run(build_research_queries(
        topic, "", None, max_queries=6, today=date(2026, 8, 17),
        round_number=2,
        gaps={"countries": ["BR"], "languages": ["pt"], "source_grades": ["A"]},
    ))

    assert queries
    assert any("BR" in query or "Brasil" in query for query in queries)
    assert any("official" in query.lower() or "gov" in query.lower() for query in queries)
