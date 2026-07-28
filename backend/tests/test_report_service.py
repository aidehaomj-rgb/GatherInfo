"""
Test report service layer using real database.
"""
from pathlib import Path
import sys
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from uuid import uuid4
from fastapi.testclient import TestClient
from fastapi import HTTPException
from app.main import create_app
from app.database import init_db, SessionLocal
from app.models import Report, Topic, SystemConfig

app = create_app()
client = TestClient(app)

_created_report_ids: list[str] = []
_created_topic_ids: list[str] = []


def setup_module():
    init_db()


def teardown_module():
    db = SessionLocal()
    try:
        for rid in _created_report_ids:
            db.query(Report).filter(Report.id == rid).delete()
        for tid in _created_topic_ids:
            db.query(Topic).filter(Topic.id == tid).delete()
        db.commit()
    finally:
        db.close()


def _unique_id(prefix: str = "test-rpt") -> str:
    return f"{prefix}-{uuid4().hex[:8]}"


def _create_test_topic(db) -> str:
    tid = f"topic-{uuid4().hex[:8]}"
    t = Topic(id=tid, name="Report Test Topic", keywords=["test"])
    db.add(t)
    db.commit()
    _created_topic_ids.append(tid)
    return tid


def _create_test_report(db, topic_id: str, content: str = "# Test Report") -> str:
    rid = _unique_id()
    r = Report(id=rid, topic_id=topic_id, title="Test Report", content=content)
    db.add(r)
    db.commit()
    _created_report_ids.append(rid)
    return rid


class TestReportService:
    """Test report_service functions."""

    def test_get_system_config_default(self):
        from app.services.report_service import get_system_config
        db = SessionLocal()
        try:
            cfg = get_system_config(db)
            assert cfg.id == "global"
        finally:
            db.close()

    def test_list_reports_all(self):
        from app.services.report_service import list_reports
        db = SessionLocal()
        try:
            reports, total = list_reports(db)
            assert isinstance(reports, list)
            assert isinstance(total, int)
        finally:
            db.close()

    def test_list_reports_by_topic(self):
        from app.services.report_service import list_reports
        db = SessionLocal()
        try:
            tid = _create_test_topic(db)
            rid = _create_test_report(db, tid)

            reports, total = list_reports(db, topic_id=tid)
            assert total >= 1
            assert any(r.id == rid for r in reports)
        finally:
            db.close()

    def test_get_report_found(self):
        from app.services.report_service import get_report
        db = SessionLocal()
        try:
            tid = _create_test_topic(db)
            rid = _create_test_report(db, tid, "# Found Report")
            r = get_report(db, rid)
            assert r.title == "Test Report"
            assert r.content == "# Found Report"
        finally:
            db.close()

    def test_get_report_not_found(self):
        from app.services.report_service import get_report
        db = SessionLocal()
        try:
            try:
                get_report(db, "nonexistent-rpt")
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 404
        finally:
            db.close()

    def test_delete_report(self):
        from app.services.report_service import delete_report, get_report
        db = SessionLocal()
        try:
            tid = _create_test_topic(db)
            rid = _create_test_report(db, tid)
            delete_report(db, rid)
            _created_report_ids.remove(rid)
            try:
                get_report(db, rid)
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 404
        finally:
            db.close()

    def test_delete_nonexistent_report(self):
        from app.services.report_service import delete_report
        db = SessionLocal()
        try:
            try:
                delete_report(db, "nonexistent-rpt")
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 404
        finally:
            db.close()

    def test_export_empty_report(self):
        from app.services.report_service import export_report_files
        db = SessionLocal()
        try:
            tid = _create_test_topic(db)
            rid = _create_test_report(db, tid, "")
            try:
                export_report_files(db, rid)
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 400
        finally:
            db.close()

    def test_download_rejects_unknown_format(self):
        from app.services.report_service import download_report_file
        db = SessionLocal()
        try:
            tid = _create_test_topic(db)
            rid = _create_test_report(db, tid, "# Has Content")
            try:
                download_report_file(rid, "exe", db)
                assert False, "Expected HTTPException"
            except HTTPException as e:
                assert e.status_code == 400
        finally:
            db.close()

    def test_download_rebuilds_missing_export_file(self, tmp_path, monkeypatch):
        import app.services.report_service as report_service

        db = SessionLocal()
        try:
            tid = _create_test_topic(db)
            rid = _create_test_report(db, tid, "# Rebuild Export")
            report = db.get(Report, rid)
            assert report is not None
            report.output_files = {"html": "'/missing/report.html'"}
            db.commit()
            config = SimpleNamespace(
                report_output_dir=str(tmp_path),
                report_dir_pattern="%Y-%m-%d",
                report_formats=["md"],
                report_title_format="{topic}_{date}",
            )
            monkeypatch.setattr(report_service, "get_system_config", lambda _: config)

            path, media_type, _ = report_service.download_report_file(rid, "html", db)

            assert path.endswith(".html")
            assert Path(path).is_file()
            assert str(path).startswith(str(tmp_path))
            assert media_type == "text/html"
        finally:
            db.close()


class TestReportAPI:
    """API-level smoke tests for reports."""

    def test_list_reports_api(self):
        resp = client.get("/api/v1/reports")
        assert resp.status_code == 200
        data = resp.json()
        assert "reports" in data

    def test_get_report_api_not_found(self):
        resp = client.get("/api/v1/reports/nonexistent-rpt")
        assert resp.status_code == 404
