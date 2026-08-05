"""Compatibility migrations for topic-scoped editorial scores."""
from sqlalchemy import create_engine, inspect, text

from app.database import Base
from app.models import CollectedItem, SourceChannel, SourceConfig, Topic
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
