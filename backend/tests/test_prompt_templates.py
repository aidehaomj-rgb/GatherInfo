"""Reusable prompt templates and topic attachment behavior."""
from pathlib import Path
import sys
from uuid import uuid4

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db
from app.engine import _topic_collection_prompt
from app.main import create_app
from app.models import PromptTemplate, Topic
from app.prompt_seed import AFRICA_CUSTOMS_RISK_PROMPT_ID, ensure_builtin_prompt_templates

client = TestClient(create_app())


def setup_module():
    init_db()


def test_prompt_crud_attachment_and_collection_merge():
    suffix = uuid4().hex[:8]
    prompt_id = f"test-prompt-{suffix}"
    topic_id = f"test-prompt-topic-{suffix}"
    created = client.post("/api/v1/prompt-templates", json={
        "id": prompt_id,
        "name": "测试采集提示词",
        "content": "重点检索海关查获与未申报货物",
    })
    assert created.status_code == 201

    topic = client.post("/api/v1/topics", json={
        "id": topic_id,
        "name": "提示词挂载测试",
        "keywords": ["海关"],
        "description_prompt": "只保留可靠来源",
        "prompt_template_ids": [prompt_id],
    })
    assert topic.status_code == 201
    assert topic.json()["prompt_template_ids"] == [prompt_id]

    db = SessionLocal()
    try:
        stored = db.query(Topic).filter(Topic.id == topic_id).one()
        merged = _topic_collection_prompt(db, stored, "最近七天")
        assert "最近七天" in merged
        assert "只保留可靠来源" in merged
        assert "重点检索海关查获与未申报货物" in merged
    finally:
        db.close()

    listed = client.get("/api/v1/prompt-templates")
    row = next(item for item in listed.json() if item["id"] == prompt_id)
    assert row["topic_count"] == 1

    assert client.delete(f"/api/v1/prompt-templates/{prompt_id}").status_code == 200
    detached = client.get(f"/api/v1/topics/{topic_id}").json()
    assert detached["prompt_template_ids"] == []
    client.delete(f"/api/v1/topics/{topic_id}")


def test_inactive_prompt_is_not_used():
    suffix = uuid4().hex[:8]
    db = SessionLocal()
    try:
        prompt = PromptTemplate(
            id=f"inactive-{suffix}", name="停用提示词", content="不应出现", is_active=False,
        )
        topic = Topic(
            id=f"inactive-topic-{suffix}", name="停用测试", keywords=["测试"],
            prompt_template_ids=[prompt.id],
        )
        db.add_all([prompt, topic])
        db.commit()
        assert "不应出现" not in _topic_collection_prompt(db, topic)
        db.delete(topic)
        db.delete(prompt)
        db.commit()
    finally:
        db.close()


def test_builtin_prompt_is_named_and_attached_to_enforcement_topic():
    db = SessionLocal()
    try:
        topic = db.query(Topic).filter(Topic.id == "weekly-enforcement-intelligence").first()
        if not topic:
            topic = Topic(id="weekly-enforcement-intelligence", name="执法信息采集", keywords=["查获"])
            db.add(topic)
            db.commit()
        ensure_builtin_prompt_templates(db)
        prompt = db.query(PromptTemplate).filter(PromptTemplate.id == AFRICA_CUSTOMS_RISK_PROMPT_ID).one()
        db.refresh(topic)
        assert prompt.name == "执法案例采集"
        assert AFRICA_CUSTOMS_RISK_PROMPT_ID in topic.prompt_template_ids
    finally:
        db.close()
