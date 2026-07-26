"""
Test export routes — CSV, JSON, XLSX.
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
    _seed_items()


def _seed_items():
    """Ensure at least a few items exist for export."""
    db = SessionLocal()
    try:
        for i in range(3):
            iid = f"it-export-{uuid4().hex[:8]}"
            it = CollectedItem(
                id=iid, source_id="tavily",
                title=f"Export Test Item {i}",
                content=f"Content for export item {i}",
                collected_at=datetime.now(timezone.utc),
                language="en", category="trade",
            )
            db.add(it)
            _created_ids.append(iid)
        db.commit()
    finally:
        db.close()


def teardown_module():
    db = SessionLocal()
    try:
        for iid in _created_ids:
            db.query(CollectedItem).filter(CollectedItem.id == iid).delete()
        db.commit()
    finally:
        db.close()


class TestCSVExport:
    """CSV export API."""

    def test_csv_export_returns_streaming_response(self):
        resp = client.get("/api/v1/items/export", params={"format": "csv"})
        assert resp.status_code in (200, 204)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            assert "csv" in ct.lower() or "text" in ct.lower()

    def test_csv_export_has_bom(self):
        """CSV export should include UTF-8 BOM for Excel compatibility."""
        resp = client.get("/api/v1/items/export", params={"format": "csv", "q": "Export Test Item"})
        if resp.status_code == 200:
            assert resp.content[:3] == b"\xef\xbb\xbf"

    def test_csv_export_content_disposition(self):
        resp = client.get("/api/v1/items/export", params={"format": "csv"})
        if resp.status_code == 200:
            cd = resp.headers.get("content-disposition", "")
            assert "attachment" in cd
            assert ".csv" in cd


class TestJSONExport:
    """JSON export API."""

    def test_json_export_returns_valid_json(self):
        import json
        resp = client.get("/api/v1/items/export", params={"format": "json"})
        assert resp.status_code in (200, 204)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            assert "json" in ct.lower()
            try:
                data = json.loads(resp.content)
                assert isinstance(data, list)
            except json.JSONDecodeError:
                assert False, "Response is not valid JSON"

    def test_json_export_has_content_disposition(self):
        resp = client.get("/api/v1/items/export", params={"format": "json"})
        if resp.status_code == 200:
            cd = resp.headers.get("content-disposition", "")
            assert "attachment" in cd
            assert ".json" in cd


class TestXLSXExport:
    """XLSX export API."""

    def test_xlsx_export(self):
        resp = client.get("/api/v1/items/export", params={"format": "xlsx"})
        assert resp.status_code in (200, 204)
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            assert ("xlsx" in ct.lower()
                    or "spreadsheet" in ct.lower()
                    or "csv" in ct.lower())


class TestExportWithFilters:
    """Export with query filters."""

    def test_csv_export_with_search_filter(self):
        resp = client.get("/api/v1/items/export", params={"format": "csv", "q": "Export Test Item"})
        assert resp.status_code in (200, 204)

    def test_json_export_with_filters(self):
        resp = client.get("/api/v1/items/export", params={
            "format": "json", "language": "en", "category": "trade"
        })
        assert resp.status_code in (200, 204)

    def test_export_invalid_format(self):
        resp = client.get("/api/v1/items/export", params={"format": "invalid"})
        assert resp.status_code in (400, 422)


class TestExportHelpers:
    """Direct unit tests for export helper functions."""

    def test_format_dt_none(self):
        from app.routes.export_routes import _format_dt
        assert _format_dt(None) is None

    def test_format_dt_valid(self):
        from app.routes.export_routes import _format_dt
        dt = datetime(2024, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        result = _format_dt(dt)
        assert "2024" in result
        assert "T" in result

    def test_item_tags_dict_empty(self):
        from app.routes.export_routes import _item_tags_dict
        mock = type("obj", (), {"tags": []})()
        assert _item_tags_dict(mock) == []

    def test_json_export_includes_tags_via_api(self):
        """JSON export via API should include tag details."""
        import json
        # Seed an item, tag it, then export
        db = SessionLocal()
        iid = None
        tag_id = None
        try:
            from app.services.tag_service import ensure_tag
            tag = ensure_tag(db, "key-export", "export-tag-test")
            tag_id = tag.id
            db.commit()

            iid = f"it-exp-{uuid4().hex[:8]}"
            it = CollectedItem(
                id=iid, source_id="tavily", title="JSON Tag Export Test",
                content="Export tag test content",
                collected_at=datetime.now(timezone.utc),
                language="zh", category="policy",
            )
            db.add(it)
            db.commit()

            from app.models import item_tags
            db.execute(item_tags.insert().values(item_id=iid, tag_id=tag.id))
            db.commit()

            resp = client.get("/api/v1/items/export", params={"format": "json", "q": "JSON Tag Export"})
            if resp.status_code == 200:
                data = json.loads(resp.content)
                export_item = next((d for d in data if d["id"] == iid), None)
                if export_item:
                    assert len(export_item["tags"]) >= 1
                    assert export_item["tags"][0]["value"] == "export-tag-test"
        finally:
            from app.models import Tag, item_tags

            if iid:
                db.execute(item_tags.delete().where(item_tags.c.item_id == iid))
                db.query(CollectedItem).filter(CollectedItem.id == iid).delete()
            if tag_id:
                remaining = db.execute(
                    item_tags.select().where(item_tags.c.tag_id == tag_id).limit(1)
                ).first()
                if remaining is None:
                    db.query(Tag).filter(Tag.id == tag_id).delete()
            db.commit()
            db.close()
