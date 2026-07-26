"""API tests for source failure diagnostics."""
from datetime import datetime, timezone
from pathlib import Path
import sys
from uuid import uuid4

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal, init_db
from app.main import create_app
from app.models import CollectionRun, SourceChannel, SourceConfig
from app.routes.items import _failure_guidance

app = create_app()
client = TestClient(app)


def test_batch_failures_classify_missing_credentials() -> None:
    init_db()
    suffix = uuid4().hex[:8]
    source_id = f"failure-source-{suffix}"
    batch_id = f"failure-batch-{suffix}"
    db = SessionLocal()
    try:
        db.add(SourceConfig(
            id=source_id, name="Failure source", channel=SourceChannel.API_SEARCH,
            base_url="https://api.example.com", is_active=True,
        ))
        db.add(CollectionRun(
            id=f"failure-run-{suffix}", source_id=source_id, batch_id=batch_id,
            status="failed", error_log=["TAVILY_API_KEY not set"],
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()

        response = client.get("/api/v1/runs/failures", params={"batch_ids": batch_id})

        assert response.status_code == 200
        detail = response.json()[0]
        assert detail["category"] == "credentials"
        assert detail["repairable"] is True
        assert "API Key" in detail["recommendation"]
    finally:
        db.query(CollectionRun).filter(CollectionRun.batch_id == batch_id).delete()
        db.query(SourceConfig).filter(SourceConfig.id == source_id).delete()
        db.commit()
        db.close()


def test_access_restriction_takes_priority_over_error_page_url() -> None:
    category, repairable, _, action = _failure_guidance([
        "HTTP error 406 Not Acceptable for https://example.com/error_404.htm"
    ], recurring_failures=10)

    assert category == "access_restricted"
    assert repairable is True
    assert action == "edit_source"
