import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.handoff_service import (
    build_material_bundle,
    push_items_to_haisee,
    start_ymg_research,
)


def _item(item_id: str):
    return SimpleNamespace(
        id=item_id,
        title=f"风险信息 {item_id}",
        content="境外海关查获一批伪报货物，报道说明了主体、货物、路线、数量与执法结果。",
        summary="境外海关查获伪报货物。",
        url=f"https://example.test/{item_id}",
        source_id="source-official",
        topic_id="topic-1",
        language="zh",
        published_at=datetime(2026, 7, 25, tzinfo=timezone.utc),
        quality_score=0.9,
        relevance_score=0.88,
        raw_metadata={"quality_review": {"decision": "approved"}},
    )


def test_material_bundle_preserves_full_evidence_and_report_context():
    report = SimpleNamespace(
        id="report-1",
        title="综合研判报告",
        summary="报告摘要",
        content="报告正文",
    )
    topic = SimpleNamespace(
        id="topic-1",
        name="境外案件",
        description="关注境外案件",
        keywords=["走私", "查获"],
    )

    bundle = build_material_bundle([_item("item-1")], topic=topic, report=report)

    assert bundle["format"] == "risk-intelligence-material-set/v1"
    assert bundle["topic"]["id"] == "topic-1"
    assert bundle["report"]["id"] == "report-1"
    assert bundle["items"][0]["content"].startswith("境外海关")
    assert bundle["items"][0]["source_url"] == "https://example.test/item-1"


def test_haisee_uses_single_and_batch_endpoints(monkeypatch):
    request = AsyncMock(side_effect=[
        {"id": "task-1", "status": "queued"},
        {"batch_id": "batch-1", "task_ids": ["task-1", "task-2"], "status": "queued"},
    ])
    monkeypatch.setattr("app.handoff_service._haisee_request", request)

    single = asyncio.run(push_items_to_haisee([_item("item-1")]))
    batch = asyncio.run(push_items_to_haisee([_item("item-1"), _item("item-2")]))

    assert single["task_ids"] == ["task-1"]
    assert batch["batch_id"] == "batch-1"
    assert request.await_args_list[0].args[0] == "/api/v1/tasks"
    assert request.await_args_list[1].args[0] == "/api/v1/tasks/batch"
    batch_payload = request.await_args_list[1].args[1]
    assert len(batch_payload["tasks"]) == 2
    assert batch_payload["tasks"][0]["meta"]["gatherinfo_item_id"] == "item-1"


def test_haisee_large_material_set_is_split_into_multiple_batches(monkeypatch):
    request = AsyncMock(side_effect=[
        {
            "batch_id": "batch-1",
            "task_ids": [f"task-{index}" for index in range(50)],
            "status": "queued",
        },
        {
            "batch_id": "batch-2",
            "task_ids": ["task-50"],
            "status": "queued",
        },
    ])
    monkeypatch.setattr("app.handoff_service._haisee_request", request)

    result = asyncio.run(
        push_items_to_haisee([_item(f"item-{index}") for index in range(51)])
    )

    assert result["batch_ids"] == ["batch-1", "batch-2"]
    assert len(result["task_ids"]) == 51
    assert len(request.await_args_list[0].args[1]["tasks"]) == 50
    assert len(request.await_args_list[1].args[1]["tasks"]) == 1


def test_ymg_handoff_sends_structured_materials_and_compatible_requirements(monkeypatch):
    post = AsyncMock(return_value={"session_id": "session-1"})
    monkeypatch.setattr("app.handoff_service._post_json", post)
    bundle = build_material_bundle([_item("item-1")])

    result = asyncio.run(start_ymg_research(
        "境外走私风险深度分析",
        bundle,
        depth="deep",
        mode="swarm",
    ))

    assert result["session_id"] == "session-1"
    payload = post.await_args.args[1]
    assert payload["materials"]["format"] == "risk-intelligence-material-set/v1"
    assert "本地情报素材集" in payload["requirements"]
    assert "item-1" in payload["requirements"]
