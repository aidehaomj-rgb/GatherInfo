"""API schema compatibility for the two-round collection loop."""
from pydantic import ValidationError
import pytest

from app.collection_schemas import (
    BatchOut,
    ActiveRunOut,
    CollectionBatchSummaryOut,
    CollectionPolicy,
    CollectResultOut,
    SourceCreate,
    SourceOut,
    SourceUpdate,
    TopicCreate,
    TopicOut,
)
from app.models import CollectionBatch


def test_collection_policy_is_typed_and_rejects_invalid_round_count() -> None:
    policy = CollectionPolicy(
        weekly_target=(10, 20),
        max_rounds=2,
        min_independent_domains=8,
        min_regions=4,
        minimum_preferred_evidence_ratio=0.6,
    )

    assert policy.max_rounds == 2
    assert policy.minimum_domains == 8
    assert policy.model_dump()["weekly_target"] == (10, 20)
    with pytest.raises(ValidationError):
        CollectionPolicy(max_rounds=3)


def test_collection_policy_accepts_flat_weekly_target_aliases() -> None:
    policy = CollectionPolicy(weekly_target_min=12, weekly_target_max=24)

    assert policy.weekly_target == (12, 24)
    assert policy.model_dump() == {"weekly_target": (12, 24)}


def test_topic_schemas_round_trip_optional_collection_policy() -> None:
    topic = TopicCreate(name="中国出口管制", collection_policy={"max_rounds": 2})
    output = TopicOut.model_validate({
        "id": "export-control",
        "name": topic.name,
        "collection_policy": topic.collection_policy.model_dump(),
    })

    assert output.collection_policy is not None
    assert output.collection_policy.max_rounds == 2


def test_collect_result_remains_compatible_and_accepts_batch_summary() -> None:
    legacy = CollectResultOut(total_items=3, items_new=2)
    summary = CollectionBatchSummaryOut(
        batch_id="batch-1",
        topic_id="export-control",
        status="completed",
        current_round=2,
        max_rounds=2,
        target={"weekly_target": 10},
        metrics={"items_new": 7},
        acceptance={"accepted": False},
        gaps=[{"type": "quantity", "missing": 3}],
        stop_reason="max_rounds_reached",
    )
    enriched = CollectResultOut(total_items=7, items_new=7, batch_summary=summary)

    assert legacy.batch_summary is None
    assert enriched.batch_summary.batch_id == "batch-1"
    batch = BatchOut(batch_id="batch-1", status="completed", batch_summary=summary)
    assert batch.batch_summary.current_round == 2
    active = ActiveRunOut(
        id="run-1",
        source_id="source-1",
        status="running",
        batch_summary=summary,
    )
    assert active.batch_summary.metrics == {"items_new": 7}
    orm_summary = CollectionBatchSummaryOut.model_validate(CollectionBatch(
        id="batch-orm",
        topic_id="export-control",
        status="running",
    ))
    assert orm_summary.batch_id == "batch-orm"


def test_source_diagnostics_are_output_only() -> None:
    diagnostic_fields = {"collection_profile", "cooldown_until", "consecutive_failures"}

    assert diagnostic_fields.isdisjoint(SourceCreate.model_fields)
    assert diagnostic_fields.isdisjoint(SourceUpdate.model_fields)
    output = SourceOut.model_validate({
        "id": "wto",
        "name": "WTO",
        "channel": "official",
        "is_active": True,
        "collection_profile": {"tier": "core", "evidence_grade": "A"},
        "consecutive_failures": 2,
    })
    assert output.collection_profile["tier"] == "core"
    assert output.consecutive_failures == 2
