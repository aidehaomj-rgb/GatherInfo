"""
Test item service layer using real database (integration tests).
"""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uuid import uuid4
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from app.main import create_app
from app.database import init_db, SessionLocal
from app.models import CollectedItem

app = create_app()
client = TestClient(app)

_created_ids: list[str] = []


def setup_module():
    init_db()


def _seed(title: str, content: str = "", **kwargs) -> str:
    """Insert a test item and return its ID."""
    db = SessionLocal()
    try:
        it = CollectedItem(
            id=kwargs.pop("id", f"it-{uuid4().hex[:12]}"),
            source_id=kwargs.pop("source_id", "tavily"),
            title=title,
            content=content,
            collected_at=kwargs.pop("collected_at", datetime.now(timezone.utc)),
            **kwargs,
        )
        db.add(it)
        db.commit()
        db.refresh(it)
        _created_ids.append(it.id)
        return it.id
    finally:
        db.close()


def teardown_module():
    db = SessionLocal()
    try:
        for cid in _created_ids:
            db.query(CollectedItem).filter(CollectedItem.id == cid).delete()
        db.commit()
    finally:
        db.close()


class TestItemService:
    """Integration tests for item_service functions against real DB."""

    def test_list_items_returns_results(self) -> None:
        from app.services.item_service import list_items
        db = SessionLocal()
        try:
            items, total = list_items(db, page=1, page_size=20)
            assert isinstance(items, list)
            assert isinstance(total, int)
            assert total >= 0
        finally:
            db.close()

    def test_list_items_with_filters(self) -> None:
        from app.services.item_service import list_items
        item_id = _seed("Customs Policy Adjustment", "About import tariff changes...")
        db = SessionLocal()
        try:
            items, total = list_items(db, page=1, page_size=20, q="Customs")
            assert total >= 1
            assert any(it.id == item_id for it in items)
        finally:
            db.close()

    def test_get_item_ids(self) -> None:
        from app.services.item_service import get_item_ids
        item_id = _seed("Test Item IDs", "ID test content")
        db = SessionLocal()
        try:
            ids, total = get_item_ids(db, q="Test Item")
            assert item_id in ids
            assert total >= 1
        finally:
            db.close()

    def test_batch_delete(self) -> None:
        from app.services.item_service import batch_delete_items
        id1 = _seed("ToDelete Alpha", "...")
        id2 = _seed("ToDelete Beta", "...")
        db = SessionLocal()
        try:
            deleted = batch_delete_items(db, [id1, id2])
            assert deleted == 2
            db.commit()
        finally:
            db.close()

        # Verify they're gone
        db2 = SessionLocal()
        try:
            for iid in [id1, id2]:
                assert db2.query(CollectedItem).filter(CollectedItem.id == iid).first() is None
        finally:
            db2.close()
        # Remove from cleanup list since already deleted
        for iid in [id1, id2]:
            if iid in _created_ids:
                _created_ids.remove(iid)

    def test_get_item_found(self) -> None:
        from app.services.item_service import get_item
        item_id = _seed("Find Me", "Findable content")
        db = SessionLocal()
        try:
            item = get_item(db, item_id)
            assert item.id == item_id
            assert item.title == "Find Me"
        finally:
            db.close()

    def test_get_item_not_found(self) -> None:
        from app.services.item_service import get_item
        from fastapi import HTTPException
        db = SessionLocal()
        try:
            try:
                get_item(db, "definitely-not-exists-99999")
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 404
        finally:
            db.close()


class TestItemAPI:
    """Test items API endpoints."""

    def test_list_items_api(self) -> None:
        resp = client.get("/api/v1/items")
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data
        assert "total" in data

    def test_latest_items_are_ordered_by_collection_time(self) -> None:
        from datetime import timedelta

        marker = f"collection-order-{uuid4().hex[:8]}"
        now = datetime.now(timezone.utc)
        newest_id = _seed(
            f"{marker} newly collected",
            "A newly collected customs intelligence article.",
            collected_at=now,
            published_at=now - timedelta(days=20),
        )
        older_id = _seed(
            f"{marker} older collection",
            "An older collection with a newer publication date.",
            collected_at=now - timedelta(days=1),
            published_at=now,
        )

        response = client.get("/api/v1/items", params={"q": marker, "page_size": 10})

        assert response.status_code == 200
        ids = [item["id"] for item in response.json()["items"]]
        assert ids.index(newest_id) < ids.index(older_id)

    def test_search_items_api(self) -> None:
        item_id = _seed("FTS Test API Item", "For testing API search")
        resp = client.get("/api/v1/items/search", params={"q": "FTS Test"})
        assert resp.status_code == 200
        data = resp.json()
        assert "items" in data

    def test_export_items_api(self) -> None:
        resp = client.get("/api/v1/items/export", params={"format": "csv"})
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "csv" in ct.lower() or "text" in ct.lower()
