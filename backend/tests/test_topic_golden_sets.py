import json
from pathlib import Path

import pytest

from app.trade_semantics import is_semantically_relevant


FIXTURE = Path(__file__).parent / "fixtures" / "topic_golden_sets.json"


def _cases(topic_id: str, label: str) -> list[str]:
    payload = json.loads(FIXTURE.read_text(encoding="utf-8"))
    return [
        f"{seed} {suffix}"
        for seed in payload["topics"][topic_id][label]
        for suffix in payload["suffixes"]
    ]


@pytest.mark.parametrize("topic_id", [
    "item-56adc0", "global-trade", "foreign-trade-forum-risk-monitoring",
    "weekly-enforcement-intelligence", "tech-regulations",
    "weekly-trade-current-affairs",
])
def test_each_optimized_topic_has_30_positive_and_30_negative_golden_cases(topic_id):
    positives = _cases(topic_id, "positive")
    negatives = _cases(topic_id, "negative")

    true_positive = sum(is_semantically_relevant(text, topic_id) for text in positives)
    false_positive = sum(is_semantically_relevant(text, topic_id) for text in negatives)
    precision = true_positive / max(1, true_positive + false_positive)
    recall = true_positive / len(positives)

    assert len(positives) >= 30
    assert len(negatives) >= 30
    assert precision >= 0.85
    assert recall >= 0.80
