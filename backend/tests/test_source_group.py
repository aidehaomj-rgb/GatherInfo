"""Isolated tests for source grouping and its runtime migration."""
from pathlib import Path
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base, get_db  # noqa: E402
from app.models import SourceConfig  # noqa: E402
from app.models_additions import migrate_schema  # noqa: E402
from app.routes.settings import export_config  # noqa: E402
from app.routes.sources import router as sources_router  # noqa: E402


def test_source_group_migration_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "legacy.db"
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE source_configs (
                id VARCHAR(80) PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                description TEXT,
                channel VARCHAR(20) NOT NULL,
                base_url VARCHAR(800),
                api_endpoint VARCHAR(800),
                homepage_url VARCHAR(800),
                default_categories JSON
            )
        """))
        conn.execute(text("""
            INSERT INTO source_configs (
                id, name, channel, base_url, default_categories
            ) VALUES (
                'legacy', 'Legacy customs source', 'RSS',
                'https://www.cbp.gov/newsroom', '["customs"]'
            )
        """))

    migrate_schema(engine)
    migrate_schema(engine)

    columns = {column["name"] for column in inspect(engine).get_columns("source_configs")}
    assert "source_group" in columns
    with engine.connect() as conn:
        group = conn.execute(text(
            "SELECT source_group FROM source_configs WHERE id = 'legacy'"
        )).scalar_one()
    assert group == "customs_enforcement"
    engine.dispose()


def test_source_group_api_roundtrip_and_filter(tmp_path: Path) -> None:
    db_path = tmp_path / "api.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    SourceConfig.__table__.create(engine)
    testing_session = sessionmaker(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app = FastAPI()
    app.include_router(sources_router)
    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)

    created = client.post("/api/v1/sources", json={
        "id": "grouped-source",
        "name": "Grouped source",
        "channel": "rss",
        "source_group": "government_igo",
    })
    assert created.status_code == 201
    assert created.json()["source_group"] == "government_igo"

    updated = client.put("/api/v1/sources/grouped-source", json={
        "source_group": "trade_commodity_data",
    })
    assert updated.status_code == 200
    assert updated.json()["source_group"] == "trade_commodity_data"

    name_only = client.put("/api/v1/sources/grouped-source", json={
        "name": "Renamed grouped source",
    })
    assert name_only.status_code == 200
    assert name_only.json()["source_group"] == "trade_commodity_data"

    matched = client.get(
        "/api/v1/sources", params={"source_group": "trade_commodity_data"}
    )
    assert matched.status_code == 200
    assert [source["id"] for source in matched.json()] == ["grouped-source"]

    missing = client.get("/api/v1/sources", params={"source_group": "other"})
    assert missing.status_code == 200
    assert missing.json() == []

    invalid = client.put("/api/v1/sources/grouped-source", json={
        "source_group": "made_up_group",
    })
    assert invalid.status_code == 400

    null_group = client.put("/api/v1/sources/grouped-source", json={
        "source_group": None,
    })
    assert null_group.status_code == 400
    assert client.get("/api/v1/sources/grouped-source").json()["source_group"] == "trade_commodity_data"
    engine.dispose()


def test_source_group_is_preserved_in_config_export(tmp_path: Path) -> None:
    db_path = tmp_path / "export.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    testing_session = sessionmaker(bind=engine)
    db = testing_session()
    try:
        db.add(SourceConfig(
            id="exported-source",
            name="Exported source",
            channel="rss",
            source_group="government_igo",
        ))
        db.commit()

        exported = export_config(db)
        source = next(
            item for item in exported["sources"]
            if item["id"] == "exported-source"
        )
        assert source["source_group"] == "government_igo"
    finally:
        db.close()
        engine.dispose()
