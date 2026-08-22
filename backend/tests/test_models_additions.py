"""Compatibility migrations for topic-scoped editorial scores."""
from sqlalchemy import create_engine, inspect, text

from app.database import Base
from app.models import (
    CollectedItem,
    CollectionBatch,
    CollectionRun,
    ItemTopicMembership,
    SourceChannel,
    SourceConfig,
    Topic,
)
from app.models_additions import migrate_schema


def test_migration_adds_and_backfills_membership_relevance(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'legacy.db'}")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE item_topic_memberships (
                item_id VARCHAR(120) NOT NULL,
                topic_id VARCHAR(80) NOT NULL,
                first_run_id VARCHAR(80),
                last_run_id VARCHAR(80),
                first_seen_at TIMESTAMP,
                last_seen_at TIMESTAMP,
                PRIMARY KEY (item_id, topic_id)
            )
        """))
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        connection.execute(
            SourceConfig.__table__.insert(),
            {"id": "source-a", "name": "Source", "channel": SourceChannel.WEB_SCRAPE},
        )
        connection.execute(
            Topic.__table__.insert(), {"id": "topic-a", "name": "Topic A"},
        )
        connection.execute(
            CollectedItem.__table__.insert(),
            {
                "id": "item-a", "source_id": "source-a", "topic_id": "topic-a",
                "title": "Item", "relevance_score": 0.82,
            },
        )
        connection.execute(text("""
            INSERT INTO item_topic_memberships (item_id, topic_id)
            VALUES ('item-a', 'topic-a')
        """))

    migrate_schema(engine)

    columns = {
        column["name"]
        for column in inspect(engine).get_columns("item_topic_memberships")
    }
    with engine.connect() as connection:
        score = connection.execute(text("""
            SELECT relevance_score FROM item_topic_memberships
            WHERE item_id = 'item-a' AND topic_id = 'topic-a'
        """)).scalar_one()
    assert "relevance_score" in columns
    assert score == 0.82
    engine.dispose()


def test_migration_adds_collection_loop_schema_to_legacy_database(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'collection-loop.db'}")
    with engine.begin() as connection:
        connection.execute(text("""
            CREATE TABLE source_configs (
                id VARCHAR(80) PRIMARY KEY,
                name VARCHAR(200) NOT NULL,
                channel VARCHAR(40) NOT NULL,
                base_url VARCHAR(800),
                api_endpoint VARCHAR(800)
            )
        """))
        connection.execute(text("""
            CREATE TABLE topics (
                id VARCHAR(80) PRIMARY KEY,
                name VARCHAR(200) NOT NULL
            )
        """))
        connection.execute(text("""
            CREATE TABLE collection_runs (
                id VARCHAR(80) PRIMARY KEY,
                source_id VARCHAR(80) NOT NULL,
                topic_id VARCHAR(80)
            )
        """))
        connection.execute(text("""
            CREATE TABLE item_topic_memberships (
                item_id VARCHAR(120) NOT NULL,
                topic_id VARCHAR(80) NOT NULL,
                PRIMARY KEY (item_id, topic_id)
            )
        """))

    migrate_schema(engine)
    migrate_schema(engine)

    inspector = inspect(engine)
    source_columns = {column["name"] for column in inspector.get_columns("source_configs")}
    topic_columns = {column["name"] for column in inspector.get_columns("topics")}
    run_columns = {column["name"] for column in inspector.get_columns("collection_runs")}
    membership_columns = {
        column["name"] for column in inspector.get_columns("item_topic_memberships")
    }

    assert {"collection_profile", "cooldown_until", "consecutive_failures"} <= source_columns
    assert "collection_policy" in topic_columns
    assert {
        "items_discovered", "items_date_rejected", "items_topic_rejected",
        "items_quality_rejected", "items_reused", "items_duplicate",
        "model_failures", "source_failures",
    } <= run_columns
    assert {
        "relevance_tier", "evidence_grade", "customs_value",
        "information_type", "relevance_metadata",
    } <= membership_columns
    assert "collection_batches" in inspector.get_table_names()
    batch_columns = {column["name"] for column in inspector.get_columns("collection_batches")}
    assert {
        "id", "topic_id", "status", "current_round", "max_rounds", "target",
        "metrics", "acceptance", "gaps", "source_plan", "round_summaries",
        "stop_reason", "created_at", "started_at", "completed_at", "updated_at",
    } <= batch_columns
    engine.dispose()


def test_collection_loop_orm_defaults_and_composite_membership_key(tmp_path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'orm.db'}")
    Base.metadata.create_all(engine)

    assert CollectionBatch.__table__.c.max_rounds.default.arg == 2
    assert SourceConfig.__table__.c.consecutive_failures.default.arg == 0
    assert CollectionRun.__table__.c.items_discovered.default.arg == 0
    assert [column.name for column in ItemTopicMembership.__table__.primary_key.columns] == [
        "item_id", "topic_id",
    ]
    engine.dispose()
