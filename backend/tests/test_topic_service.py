"""
Test topic service layer using real database.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uuid import uuid4
from fastapi.testclient import TestClient
from fastapi import HTTPException
from app.main import create_app
from app.database import init_db, SessionLocal
from app.models import Topic

app = create_app()
client = TestClient(app)

_created_ids: list[str] = []


def setup_module():
    init_db()


def teardown_module():
    db = SessionLocal()
    try:
        for tid in _created_ids:
            db.query(Topic).filter(Topic.id == tid).delete()
        db.commit()
    finally:
        db.close()


def _unique_id() -> str:
    return f"test-topic-{uuid4().hex[:8]}"


class TestNormalizeKeywords:
    """Keyword normalization logic."""

    def test_strips_and_dedups(self):
        from app.services.topic_service import _normalize_keywords
        result = _normalize_keywords(["  tariff  ", "sanctions", ""])
        assert result == ["tariff", "sanctions"]

    def test_normalizes_punctuation(self):
        from app.services.topic_service import _normalize_keywords
        result = _normalize_keywords(["政策，法规", "关税：进口"])
        assert result == ["政策", "法规", "关税:进口"]

    def test_splits_common_keyword_separators(self):
        from app.services.topic_service import _normalize_keywords
        result = _normalize_keywords(["关税；走私、出口管制;贸易救济"])
        assert result == ["关税", "走私", "出口管制", "贸易救济"]


class TestTopicServiceCRUD:
    """Test topic_service CRUD functions."""

    def test_create_topic(self):
        from app.services.topic_service import create_topic
        tid = _unique_id()
        db = SessionLocal()
        try:
            t = create_topic(db, {"id": tid, "name": "Test Topic", "keywords": ["trade", "tariff"]})
            _created_ids.append(tid)
            assert t.id == tid
            assert t.name == "Test Topic"
            assert t.keywords == ["trade", "tariff"]
        finally:
            db.close()

    def test_create_topic_auto_id(self):
        from app.services.topic_service import create_topic
        db = SessionLocal()
        try:
            t = create_topic(db, {"name": "Auto Topic", "keywords": ["test"]})
            _created_ids.append(t.id)
            assert t.id.startswith("topic-")
        finally:
            db.close()

    def test_create_topic_duplicate(self):
        from app.services.topic_service import create_topic
        tid = _unique_id()
        db = SessionLocal()
        try:
            create_topic(db, {"id": tid, "name": "Dup", "keywords": ["a"]})
            _created_ids.append(tid)
            try:
                create_topic(db, {"id": tid, "name": "Dup2", "keywords": ["b"]})
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 400
        finally:
            db.close()

    def test_update_topic(self):
        from app.services.topic_service import create_topic, update_topic
        tid = _unique_id()
        db = SessionLocal()
        try:
            create_topic(db, {"id": tid, "name": "Before", "keywords": ["old"]})
            _created_ids.append(tid)
            updated = update_topic(db, tid, {"name": "After"})
            assert updated.name == "After"
            assert updated.keywords == ["old"]
        finally:
            db.close()

    def test_update_topic_normalizes_keywords(self):
        from app.services.topic_service import create_topic, update_topic
        tid = _unique_id()
        db = SessionLocal()
        try:
            create_topic(db, {"id": tid, "name": "KW Norm", "keywords": ["a"]})
            _created_ids.append(tid)
            updated = update_topic(db, tid, {"keywords": ["关税，进口", ""]})
            assert updated.keywords == ["关税", "进口"]
        finally:
            db.close()

    def test_update_nonexistent(self):
        from app.services.topic_service import update_topic
        db = SessionLocal()
        try:
            try:
                update_topic(db, "nonexistent-topic", {"name": "X"})
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 404
        finally:
            db.close()

    def test_delete_topic(self):
        from app.services.topic_service import create_topic, delete_topic, get_topic
        tid = _unique_id()
        db = SessionLocal()
        try:
            create_topic(db, {"id": tid, "name": "ToDelete", "keywords": ["test"]})
            delete_topic(db, tid)
            try:
                get_topic(db, tid)
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 404
        finally:
            db.close()

    def test_delete_nonexistent(self):
        from app.services.topic_service import delete_topic
        db = SessionLocal()
        try:
            try:
                delete_topic(db, "nonexistent-topic")
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 404
        finally:
            db.close()

    def test_get_topic_found(self):
        from app.services.topic_service import create_topic, get_topic
        tid = _unique_id()
        db = SessionLocal()
        try:
            create_topic(db, {"id": tid, "name": "FindMe", "keywords": ["test"]})
            _created_ids.append(tid)
            t = get_topic(db, tid)
            assert t.name == "FindMe"
        finally:
            db.close()

    def test_get_topic_not_found(self):
        from app.services.topic_service import get_topic
        db = SessionLocal()
        try:
            try:
                get_topic(db, "nonexistent")
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 404
        finally:
            db.close()

    def test_list_topics(self):
        from app.services.topic_service import list_topics
        db = SessionLocal()
        try:
            topics = list_topics(db)
            assert isinstance(topics, list)
        finally:
            db.close()


class TestTopicAPI:
    """API-level smoke tests for topics."""

    def test_list_topics_api(self):
        resp = client.get("/api/v1/topics")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_create_and_delete_topic_api(self):
        tid = _unique_id()
        resp = client.post("/api/v1/topics", json={
            "id": tid, "name": "API Topic",
            "keywords": ["trade", "exports"],
        })
        assert resp.status_code in (200, 201)
        assert resp.json()["id"] == tid

        resp2 = client.delete(f"/api/v1/topics/{tid}")
        assert resp2.status_code == 200
