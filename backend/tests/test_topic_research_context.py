from datetime import date
from types import SimpleNamespace

import pytest

from app.topic_research_context import (
    SIX_OPTIMIZED_TOPIC_IDS,
    build_topic_research_context,
)


def _topic(**overrides):
    values = {
        "id": "global-trade",
        "name": "关税类贸易政策",
        "description": "跟踪关税与贸易救济政策",
        "keywords": ["关税", "tariff"],
        "synonyms": ["customs duty"],
        "exclude_keywords": ["招聘"],
        "categories": ["tariff", "trade"],
        "focus_countries": ["US", "EU"],
        "focus_languages": ["en", "zh"],
        "target_urls": ["https://www.wto.org/"],
        "target_urls_mode": "explicit",
        "description_prompt": "区分政策阶段",
        "collect_window_days": 14,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_context_is_immutable_and_preserves_all_topic_inputs() -> None:
    context = build_topic_research_context(
        _topic(),
        prompt="补充检索原产地规则",
        window_start=date(2026, 8, 1),
        window_end=date(2026, 8, 15),
    )

    assert context.keywords == ("关税", "tariff")
    assert context.synonyms == ("customs duty",)
    assert context.exclude_keywords == ("招聘",)
    assert context.categories == ("tariff", "trade")
    assert context.focus_countries == ("US", "EU")
    assert context.focus_languages == ("en", "zh")
    assert context.target_urls == ("https://www.wto.org/",)
    assert context.target_urls_mode == "explicit"
    assert "区分政策阶段" in context.prompt
    assert "补充检索原产地规则" in context.prompt
    assert context.window.start == date(2026, 8, 1)
    assert context.policy.max_rounds == 2
    assert context.policy.weekly_target == (15, 30)
    assert context.literal_keyword_bypass_allowed is False
    with pytest.raises((AttributeError, TypeError)):
        context.keywords += ("mutate",)


def test_all_six_topics_have_explicit_collection_and_review_defaults() -> None:
    assert SIX_OPTIMIZED_TOPIC_IDS == frozenset({
        "item-56adc0", "global-trade", "foreign-trade-forum-risk-monitoring",
        "weekly-enforcement-intelligence", "tech-regulations",
        "weekly-trade-current-affairs",
    })
    for topic_id in SIX_OPTIMIZED_TOPIC_IDS:
        context = build_topic_research_context(_topic(id=topic_id))
        assert context.search_dimensions
        assert context.document_types
        assert context.source_grades
        assert 0 <= context.policy.minimum_quality <= 1
        assert context.policy.minimum_domains > 0
        assert context.policy.max_rounds == 2


def test_context_serialization_is_json_safe_and_does_not_expose_mutable_state() -> None:
    context = build_topic_research_context(_topic())
    payload = context.to_dict()
    payload["keywords"].append("changed")

    assert context.keywords == ("关税", "tariff")
    assert payload["relevance_tiers"] == [
        "china_direct", "china_transmission", "global_reference",
    ]
    assert payload["evidence_grades"] == ["A", "B", "C"]
