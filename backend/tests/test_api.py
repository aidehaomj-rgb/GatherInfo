"""
GatherInfo backend tests — collection engine, API, tag system.
"""
from pathlib import Path
import sys
from datetime import datetime, timezone

from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.main import create_app  # noqa: E402
from app.database import SessionLocal, init_db  # noqa: E402
from app.models import CollectionRun, JobStatus  # noqa: E402

app = create_app()
client = TestClient(app)


def setup_module():
    """Create tables before running tests."""
    init_db()


# ── Health ──────────────────────────────────────────────────────────

def test_health() -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ── Sources ─────────────────────────────────────────────────────────

def test_list_sources() -> None:
    resp = client.get("/api/v1/sources")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_create_and_delete_source() -> None:
    resp = client.post("/api/v1/sources", json={
        "id": "test-source", "name": "Test Source", "channel": "api_search",
    })
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert data["id"] == "test-source"
    assert data["channel"] == "api_search"

    # Delete
    resp2 = client.delete("/api/v1/sources/test-source")
    assert resp2.status_code == 200
    assert resp2.json()["ok"] is True


# ── Topics ──────────────────────────────────────────────────────────

def test_create_and_list_topics() -> None:
    resp = client.post("/api/v1/topics", json={
        "id": "test-topic", "name": "Test Topic",
        "keywords": ["test", "测试"],
        "auto_tag_rules": [{"keyword": "test", "tag": "category:test"}],
    })
    assert resp.status_code in (200, 201)
    assert resp.json()["id"] == "test-topic"

    resp2 = client.get("/api/v1/topics")
    assert resp2.status_code == 200
    ids = [t["id"] for t in resp2.json()]
    assert "test-topic" in ids

    # Delete
    resp3 = client.delete("/api/v1/topics/test-topic")
    assert resp3.status_code == 200


# ── Collection ──────────────────────────────────────────────────────

def test_collect_nonexistent_topic() -> None:
    resp = client.post("/api/v1/collect", json={"topic_id": "nonexistent"})
    assert resp.status_code in (400, 404, 422)


# ── Items ───────────────────────────────────────────────────────────

def test_list_items() -> None:
    resp = client.get("/api/v1/items")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert "total" in data


def test_quality_review_deletes_known_low_value_page() -> None:
    from app.database import SessionLocal
    from app.models import CollectedItem

    source = client.post("/api/v1/sources", json={
        "id": "quality-review-source", "name": "Quality Review Source", "channel": "api_search",
    })
    assert source.status_code in (200, 201)
    db = SessionLocal()
    try:
        db.add(CollectedItem(
            id="quality-review-noise", source_id="quality-review-source",
            title="查获_【环球博讯】",
            content="BOSS体育 U存U取 编辑推荐 SIDE1 招租 Copyright 环球博彩资讯门户网",
            url="https://m.wgi888.com/tag/%E6%9F%A5%E8%8E%B7",
        ))
        db.commit()
    finally:
        db.close()

    response = client.post("/api/v1/items/quality-review", json={
        "item_ids": ["quality-review-noise"], "limit": 1,
    })
    assert response.status_code == 200
    assert response.json()["deleted"] == 1
    client.delete("/api/v1/sources/quality-review-source")


# ── Tags ────────────────────────────────────────────────────────────

def test_list_tags() -> None:
    resp = client.get("/api/v1/tags")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_tag_stats() -> None:
    resp = client.get("/api/v1/tags/stats")
    assert resp.status_code == 200


# ── Stats ───────────────────────────────────────────────────────────

def test_stats() -> None:
    resp = client.get("/api/v1/stats")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("total_sources", "total_topics", "total_items"):
        assert key in data


def test_dashboard() -> None:
    resp = client.get("/api/v1/stats/dashboard")
    assert resp.status_code == 200
    data = resp.json()
    assert "summary" in data
    assert "daily_trend" in data
    assert "topic_stats" in data
    assert isinstance(data["topic_stats"], list)


def test_topic_ai_collection_strategy_round_trips() -> None:
    payload = {
        "id": "test-ai-collection-topic",
        "name": "AI Collection Topic",
        "keywords": ["test"],
        "description_prompt": "检索近一周的高价值贸易风险信息。",
        "ai_research_model_id": "configured-model",
    }
    created = client.post("/api/v1/topics", json=payload)
    assert created.status_code in (200, 201)
    body = created.json()
    assert body["description_prompt"] == payload["description_prompt"]
    assert body["ai_research_model_id"] == payload["ai_research_model_id"]
    assert client.delete("/api/v1/topics/test-ai-collection-topic").status_code == 200


# ── Connectors ──────────────────────────────────────────────────────

def test_connectors() -> None:
    resp = client.get("/api/v1/connectors")
    assert resp.status_code == 200
    channels = [c["channel"] for c in resp.json()]
    assert "api_search" in channels
    assert "web_scrape" in channels


# ── Seed ────────────────────────────────────────────────────────────

def test_seed_defaults() -> None:
    resp = client.post("/api/v1/seed-defaults")
    assert resp.status_code == 200
    assert resp.json()["models_created"] == 0


# ── Auto-ID (信息员 / 主题) ──────────────────────────────────────────

def test_create_source_auto_id() -> None:
    """SourceCreate without id should auto-generate a slugified id."""
    resp = client.post("/api/v1/sources", json={
        "name": "Auto ID Reporter", "channel": "api_search",
    })
    assert resp.status_code in (200, 201)
    data = resp.json()
    sid = data["id"]
    assert sid  # non-empty
    assert sid == sid.lower()  # slug is lowercased
    assert " " not in sid  # spaces removed
    client.delete(f"/api/v1/sources/{sid}")


def test_create_topic_auto_id() -> None:
    """TopicCreate without id should auto-generate an id."""
    resp = client.post("/api/v1/topics", json={
        "name": "Auto ID Topic", "keywords": ["auto"],
    })
    assert resp.status_code in (200, 201)
    data = resp.json()
    tid = data["id"]
    assert tid
    # New schema fields present on output
    assert "source_names" in data
    assert "auto_report" in data
    client.delete(f"/api/v1/topics/{tid}")


def test_create_topic_with_auto_report_and_sources() -> None:
    """Topic with source binding + auto_report should round-trip."""
    s = client.post("/api/v1/sources", json={"name": "Bound Reporter", "channel": "api_search"})
    sid = s.json()["id"]
    resp = client.post("/api/v1/topics", json={
        "name": "Auto Report Topic",
        "keywords": ["x"],
        "source_ids": [sid],
        "auto_report": True,
    })
    assert resp.status_code in (200, 201)
    data = resp.json()
    tid = data["id"]
    assert data["auto_report"] is True
    assert sid in data.get("source_ids", [])
    assert "Bound Reporter" in data.get("source_names", [])
    client.delete(f"/api/v1/topics/{tid}")
    client.delete(f"/api/v1/sources/{sid}")


# ── Runs ────────────────────────────────────────────────────────────

def test_list_runs() -> None:
    resp = client.get("/api/v1/runs")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


def test_active_runs_include_rich_progress_events() -> None:
    client.delete("/api/v1/sources/progress-test-source")
    source = client.post("/api/v1/sources", json={
        "id": "progress-test-source",
        "name": "实时进度测试源",
        "channel": "web_scrape",
        "base_url": "https://example.com",
    })
    assert source.status_code == 201

    db = SessionLocal()
    try:
        db.add(CollectionRun(
            id="progress-test-run",
            source_id="progress-test-source",
            status=JobStatus.RUNNING,
            batch_id="progress-test-batch",
            started_at=datetime.now(timezone.utc),
            progress_events=[{
                "stage": "discovered",
                "status": "running",
                "message": "发现候选信息：《测试文章》",
                "item_title": "测试文章",
                "detail": {"url": "https://example.com/article"},
                "created_at": datetime.now(timezone.utc).isoformat(),
            }],
        ))
        db.add(CollectionRun(
            id="progress-test-completed-run",
            source_id="progress-test-source",
            status=JobStatus.COMPLETED,
            batch_id="progress-test-batch",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        ))
        db.commit()

        response = client.get("/api/v1/runs/active")
        assert response.status_code == 200
        active = next(run for run in response.json() if run["id"] == "progress-test-run")
        assert active["source_name"] == "实时进度测试源"
        assert active["progress_events"][0]["stage"] == "discovered"
        assert active["progress_events"][0]["item_title"] == "测试文章"
        assert active["batch_total_sources"] == 2
        assert active["batch_completed_sources"] == 1
        assert active["batch_active_sources"] == 1
    finally:
        db.query(CollectionRun).filter(CollectionRun.batch_id == "progress-test-batch").delete()
        db.commit()
        db.close()
        client.delete("/api/v1/sources/progress-test-source")


# ── Report scope + batch ────────────────────────────────────────────

def test_generate_report_invalid_topic() -> None:
    resp = client.post("/api/v1/reports/generate", json={"topic_id": "nonexistent-topic-xyz"})
    assert resp.status_code in (400, 404, 500)


def test_generate_report_accepts_scope_params() -> None:
    """Endpoint should accept collection_run_id / date range without 422."""
    resp = client.post("/api/v1/reports/generate", json={
        "topic_id": "nonexistent-topic-xyz",
        "collection_run_id": "run-xyz",
        "date_from": "2024-01-01",
        "date_to": "2024-12-31",
    })
    # Not a validation error — topic missing yields 400/404/500
    assert resp.status_code != 422


def test_batch_generate_empty() -> None:
    resp = client.post("/api/v1/reports/batch-generate", json={"topic_ids": []})
    assert resp.status_code in (400, 422)   # 422 from Pydantic min_length validation


def test_batch_generate_structure() -> None:
    """Batch generate returns results + failed count even when topics fail."""
    resp = client.post("/api/v1/reports/batch-generate", json={
        "topic_ids": ["nonexistent-a", "nonexistent-b"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert "failed" in data
    assert isinstance(data["failed"], int)


# ── Model auto-discover ─────────────────────────────────────────────

def test_auto_discover_models() -> None:
    """Auto-discover returns a providers list (may be empty if no servers)."""
    resp = client.post("/api/v1/models/auto-discover")
    assert resp.status_code == 200
    data = resp.json()
    assert "providers" in data
    assert isinstance(data["providers"], list)


def test_list_ollama_cloud_models_uses_cloud_api(monkeypatch) -> None:
    """Ollama Cloud model discovery should use the native cloud API with auth."""
    requests: list[dict[str, object]] = []

    class _Response:
        status_code = 200
        text = ""

        def json(self):
            return {"models": [{"name": "gpt-oss:20b"}, {"name": "llama3.3"}]}

    class _Client:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, traceback):
            return None

        async def get(self, url, headers=None):
            requests.append({"url": url, "headers": headers or {}})
            return _Response()

    monkeypatch.setattr("app.routes.models.httpx.AsyncClient", _Client)

    resp = client.post("/api/v1/models/list-available", json={
        "provider": "ollama_cloud",
        "base_url": "https://ollama.com",
        "api_key": "test-cloud-key",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["models"] == ["gpt-oss:20b", "llama3.3"]
    assert requests == [{
        "url": "https://ollama.com/api/tags",
        "headers": {"Authorization": "Bearer test-cloud-key"},
    }]


# ── Tag merge ───────────────────────────────────────────────────────

def test_tag_merge_same_tag_rejected() -> None:
    resp = client.post("/api/v1/tags/merge", json={
        "source_tag_id": "x", "target_tag_id": "x",
    })
    assert resp.status_code == 400


def test_tag_merge_missing_tag() -> None:
    resp = client.post("/api/v1/tags/merge", json={
        "source_tag_id": "missing-a", "target_tag_id": "missing-b",
    })
    assert resp.status_code == 404


def test_tag_merge_moves_and_deletes() -> None:
    """Merging source into target deletes source and reports moved items."""
    from app.database import SessionLocal
    from app.models import Tag

    db = SessionLocal()
    try:
        for tid in ("merge:src", "merge:dst"):
            if not db.query(Tag).filter(Tag.id == tid).first():
                ns, val = tid.split(":")
                db.add(Tag(id=tid, namespace=ns, value=val))
        db.commit()
    finally:
        db.close()

    resp = client.post("/api/v1/tags/merge", json={
        "source_tag_id": "merge:src", "target_tag_id": "merge:dst",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["target_tag_id"] == "merge:dst"
    assert data["deleted_tag_id"] == "merge:src"
    assert isinstance(data["moved_items"], int)

    # Source tag must be gone
    db = SessionLocal()
    try:
        assert db.query(Tag).filter(Tag.id == "merge:src").first() is None
        db.query(Tag).filter(Tag.id == "merge:dst").delete()
        db.commit()
    finally:
        db.close()


# ── Persistence ─────────────────────────────────────────────────────

def test_persistence_survives_new_session() -> None:
    """A created source must be readable via a fresh DB session."""
    from app.database import SessionLocal
    from app.models import SourceConfig

    r = client.post("/api/v1/sources", json={"name": "Persisted Reporter", "channel": "api_search"})
    sid = r.json()["id"]

    db = SessionLocal()
    try:
        assert db.query(SourceConfig).filter(SourceConfig.id == sid).first() is not None
    finally:
        db.close()

    client.delete(f"/api/v1/sources/{sid}")


# ── Punctuation tolerance (中文标点) ─────────────────────────────────

def test_topic_chinese_punctuation_normalized() -> None:
    """Chinese commas/colons in topic payload should be normalized to ASCII."""
    resp = client.post("/api/v1/topics", json={
        "id": "punct-topic",
        "name": "标点测试",
        "keywords": ["关税，走私，价格"],
        "auto_tag_rules": [{"keyword": "关税：税则", "tag": "category：政策"}],
        "keyword_tags": [{"keyword": "缉私，执法", "weight": 1.0}],
    })
    assert resp.status_code in (200, 201)
    data = resp.json()
    # Chinese comma split into multiple keywords
    assert "关税" in data["keywords"]
    assert "走私" in data["keywords"]
    assert "价格" in data["keywords"]
    # Chinese colon in auto_tag_rules normalized to ASCII
    rule = data["auto_tag_rules"][0]
    assert "：" not in rule["keyword"]
    assert "：" not in rule["tag"]
    # keyword_tags Chinese comma split
    kt_keywords = [k["keyword"] for k in data.get("keyword_tags", [])]
    assert "缉私" in kt_keywords or "执法" in kt_keywords
    client.delete("/api/v1/topics/punct-topic")


def test_topic_keyword_list_accepts_semicolons_and_enumeration_marks() -> None:
    """Topic keywords may use common Chinese and English list separators."""
    resp = client.post("/api/v1/topics", json={
        "id": "keyword-separator-topic",
        "name": "关键词间隔测试",
        "keywords": ["关税；走私、出口管制;贸易救济"],
    })
    assert resp.status_code in (200, 201)
    assert resp.json()["keywords"] == ["关税", "走私", "出口管制", "贸易救济"]
    client.delete("/api/v1/topics/keyword-separator-topic")


# ── Source homepage_url roundtrip ───────────────────────────────────

def test_source_homepage_url_roundtrip() -> None:
    resp = client.post("/api/v1/sources", json={
        "name": "Homepage Source", "channel": "web_scrape",
        "homepage_url": "https://example.com/home",
    })
    assert resp.status_code in (200, 201)
    data = resp.json()
    sid = data["id"]
    assert data["homepage_url"] == "https://example.com/home"
    # Fetch back
    got = client.get(f"/api/v1/sources/{sid}")
    assert got.json()["homepage_url"] == "https://example.com/home"
    client.delete(f"/api/v1/sources/{sid}")


# ── collect_window_days default + update ────────────────────────────

def test_topic_collect_window_days() -> None:
    # Default value is 7
    resp = client.post("/api/v1/topics", json={
        "name": "Window Topic", "keywords": ["w"],
    })
    assert resp.status_code in (200, 201)
    data = resp.json()
    tid = data["id"]
    assert data["collect_window_days"] == 7
    # Update to a custom window
    upd = client.put(f"/api/v1/topics/{tid}", json={"collect_window_days": 30})
    assert upd.status_code == 200
    assert upd.json()["collect_window_days"] == 30


def test_topic_focus_languages_can_be_updated() -> None:
    tid = "multilingual-topic"
    created = client.post("/api/v1/topics", json={"id": tid, "name": "Multilingual"})
    assert created.status_code == 201

    updated = client.put(
        f"/api/v1/topics/{tid}",
        json={"focus_languages": ["zh", "en", "es"], "focus_countries": ["CN", "US"]},
    )
    assert updated.status_code == 200
    assert updated.json()["focus_languages"] == ["zh", "en", "es"]
    assert updated.json()["focus_countries"] == ["CN", "US"]
    client.delete(f"/api/v1/topics/{tid}")


# ── System settings GET/PUT ─────────────────────────────────────────

def test_settings_get_default() -> None:
    resp = client.get("/api/v1/settings")
    assert resp.status_code == 200
    data = resp.json()
    assert "report_title_format" in data
    assert "report_formats" in data
    assert isinstance(data["report_formats"], list)


def test_settings_update() -> None:
    resp = client.put("/api/v1/settings", json={
        "report_title_format": "{topic}-{date}-报告",
        "report_dir_pattern": "%Y/%m",
        "report_formats": ["md", "pdf"],
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["report_title_format"] == "{topic}-{date}-报告"
    assert data["report_dir_pattern"] == "%Y/%m"
    assert set(data["report_formats"]) == {"md", "pdf"}
    # Restore defaults to avoid leaking state to other tests
    client.put("/api/v1/settings", json={
        "report_title_format": "{topic}_情报报告_{date}",
        "report_dir_pattern": "%Y-%m-%d",
        "report_formats": ["md", "html", "docx", "pdf"],
    })


# ── Report export file generation ───────────────────────────────────

def test_report_export_generates_files(tmp_path) -> None:
    """export_report should render the configured formats to disk."""
    from types import SimpleNamespace
    from app.report_export import export_report

    report = SimpleNamespace(
        content="# 标题\n\n## 小节\n\n- 条目一\n- 条目二\n\n正文段落，中文与 English 混排。",
        title="导出测试",
        topic_id="t-export",
        output_files=None,
        output_dir=None,
    )
    system = SimpleNamespace(
        report_output_dir=str(tmp_path),
        report_dir_pattern="%Y-%m-%d",
        report_formats=["md", "html", "docx", "pdf"],
        report_title_format="{topic}_情报报告_{date}",
    )
    topic = SimpleNamespace(name="导出主题")
    out = export_report(report, system, topic)
    assert set(out.keys()) == {"md", "html", "docx", "pdf"}
    for fmt, path in out.items():
        p = Path(path)
        assert p.exists()
        assert p.stat().st_size > 0
    # report object updated with output metadata
    assert report.output_files == out
    assert report.output_dir
