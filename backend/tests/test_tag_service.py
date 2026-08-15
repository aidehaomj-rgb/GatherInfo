"""
Test tag service layer using real database.
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uuid import uuid4
from fastapi.testclient import TestClient
from fastapi import HTTPException
from app.main import create_app
from app.database import init_db, SessionLocal
from app.models import Tag, item_tags, CollectedItem

app = create_app()
client = TestClient(app)

_created_tag_ids: list[str] = []
_created_item_ids: list[str] = []


def setup_module():
    init_db()


def teardown_module():
    db = SessionLocal()
    try:
        for itid in _created_item_ids:
            db.execute(item_tags.delete().where(item_tags.c.item_id == itid))
            db.query(CollectedItem).filter(CollectedItem.id == itid).delete()
        for tid in _created_tag_ids:
            db.query(Tag).filter(Tag.id == tid).delete()
        db.commit()
    finally:
        db.close()


def _create_test_item(db, title: str = "Tag Test Item") -> str:
    from datetime import datetime, timezone
    iid = f"it-{uuid4().hex[:12]}"
    it = CollectedItem(
        id=iid, source_id="tavily", title=title,
        content="Test content for tag service",
        collected_at=datetime.now(timezone.utc),
    )
    db.add(it)
    db.commit()
    _created_item_ids.append(iid)
    return iid


class TestEnsureTag:
    """ensure_tag creates or retrieves tags."""

    def test_ensure_tag_new(self):
        from app.services.tag_service import ensure_tag
        db = SessionLocal()
        try:
            tag = ensure_tag(db, "category", "test-new-tag")
            db.commit()
            _created_tag_ids.append(tag.id)
            assert tag.namespace == "category"
            assert tag.value == "test-new-tag"
            assert tag.id.startswith("tag-")
        finally:
            db.close()

    def test_ensure_tag_existing(self):
        from app.services.tag_service import ensure_tag
        db = SessionLocal()
        try:
            tag1 = ensure_tag(db, "keyword", "reuse-me")
            db.commit()
            _created_tag_ids.append(tag1.id)
            tag2 = ensure_tag(db, "keyword", "reuse-me")
            assert tag1.id == tag2.id
        finally:
            db.close()

    def test_rejects_date_with_mojibake_question_marks(self):
        from app.services.tag_service import ensure_tag
        db = SessionLocal()
        try:
            try:
                ensure_tag(db, "portfolio", "2026-08-13????")
                assert False, "Expected HTTPException"
            except HTTPException as exc:
                assert exc.status_code == 422
            assert db.query(Tag).filter(Tag.value == "2026-08-13????").first() is None
        finally:
            db.close()

    def test_rejects_plain_date_tag(self):
        from app.services.tag_service import ensure_tag
        db = SessionLocal()
        try:
            try:
                ensure_tag(db, "event", "2026-08-13")
                assert False, "Expected HTTPException"
            except HTTPException as exc:
                assert exc.status_code == 422
            assert db.query(Tag).filter(Tag.value == "2026-08-13").first() is None
        finally:
            db.close()


class TestTagServiceCRUD:
    """Test tag_service update/delete."""

    def test_update_tag(self):
        from app.services.tag_service import ensure_tag, update_tag
        db = SessionLocal()
        try:
            tag = ensure_tag(db, "src", "update-test")
            db.commit()
            _created_tag_ids.append(tag.id)
            updated = update_tag(db, tag.id, {"label": "NewLabel"})
            assert updated.label == "NewLabel"
            assert updated.value == "update-test"
        finally:
            db.close()

    def test_update_nonexistent(self):
        from app.services.tag_service import update_tag
        db = SessionLocal()
        try:
            try:
                update_tag(db, "nonexistent-tag-xyz", {"label": "X"})
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 404
        finally:
            db.close()

    def test_update_rejects_mojibake_label(self):
        from app.services.tag_service import ensure_tag, update_tag
        db = SessionLocal()
        try:
            tag = ensure_tag(db, "src", "valid-update-target")
            db.commit()
            _created_tag_ids.append(tag.id)
            try:
                update_tag(db, tag.id, {"label": "2026-08-13????"})
                assert False, "Expected HTTPException"
            except HTTPException as exc:
                assert exc.status_code == 422
        finally:
            db.close()

    def test_delete_tag(self):
        from app.services.tag_service import ensure_tag, delete_tag
        db = SessionLocal()
        try:
            tag = ensure_tag(db, "src", "del-me")
            db.commit()
            tid = tag.id
            _created_tag_ids.append(tid)
            delete_tag(db, tid)
            exists = db.query(Tag).filter(Tag.id == tid).first()
            assert exists is None
            _created_tag_ids.remove(tid)
        finally:
            db.close()

    def test_delete_nonexistent(self):
        from app.services.tag_service import delete_tag
        db = SessionLocal()
        try:
            try:
                delete_tag(db, "nonexistent-tag-xyz")
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 404
        finally:
            db.close()


class TestTagServiceList:
    """Test tag listing."""

    def test_list_tags_all(self):
        from app.services.tag_service import list_tags
        db = SessionLocal()
        try:
            tags = list_tags(db)
            assert isinstance(tags, list)
        finally:
            db.close()

    def test_list_tags_by_namespace(self):
        from app.services.tag_service import list_tags, ensure_tag
        db = SessionLocal()
        try:
            tag = ensure_tag(db, "custom-ns-test", "ns-filter-val")
            db.commit()
            _created_tag_ids.append(tag.id)
            tags = list_tags(db, namespace="custom-ns-test")
            assert any(t.id == tag.id for t in tags)
        finally:
            db.close()


class TestTagMerge:
    """Test tag merging."""

    def test_merge_tags_moves_items(self):
        from app.services.tag_service import ensure_tag, merge_tags
        db = SessionLocal()
        try:
            src = ensure_tag(db, "key", "merge-src-val")
            dst = ensure_tag(db, "key", "merge-dst-val")
            db.commit()
            _created_tag_ids.extend([src.id, dst.id])

            iid = _create_test_item(db, "Merge Test Item")
            db.execute(item_tags.insert().values(item_id=iid, tag_id=src.id))
            # dst already has item via auto-tag or similar in real scenario
            db.commit()

            result = merge_tags(db, src.id, dst.id)
            assert result["target_tag_id"] == dst.id
            assert result["moved_items"] >= 1

            # Source tag should be deleted
            assert db.query(Tag).filter(Tag.id == src.id).first() is None
            _created_tag_ids.remove(src.id)
        finally:
            db.close()

    def test_merge_nonexistent_source(self):
        from app.services.tag_service import merge_tags
        db = SessionLocal()
        try:
            try:
                merge_tags(db, "nonexistent-src-xyz", "nonexistent-dst-xyz")
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 404
        finally:
            db.close()


class TestTagStats:
    """Test tag statistics."""

    def test_tag_stats_returns_list(self):
        from app.services.tag_service import tag_stats
        db = SessionLocal()
        try:
            stats = tag_stats(db, limit=10)
            assert isinstance(stats, list)
        finally:
            db.close()


class TestTagAPI:
    """API-level smoke tests for tags."""

    def test_list_tags_api(self):
        resp = client.get("/api/v1/tags")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_tag_stats_api(self):
        resp = client.get("/api/v1/tags/stats")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_update_rejects_plain_date_label(self):
        resp = client.put("/api/v1/tags/category%3Atrade", json={"label": "2026-08-13"})
        assert resp.status_code == 422
        assert resp.json()["detail"] == "标签内容无效或包含乱码"

    def test_merge_tags_api(self):
        from app.services.tag_service import ensure_tag
        db = SessionLocal()
        try:
            src = ensure_tag(db, "key-mergetest", "api-src-val")
            dst = ensure_tag(db, "key-mergetest", "api-dst-val")
            db.commit()  # CRITICAL: commit so API's separate session can see tags
            _created_tag_ids.extend([src.id, dst.id])
        finally:
            db.close()

        resp = client.post("/api/v1/tags/merge", json={
            "source_tag_id": src.id,
            "target_tag_id": dst.id,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["target_tag_id"] == dst.id
        _created_tag_ids.remove(src.id)
