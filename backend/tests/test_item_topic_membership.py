from datetime import datetime, timezone
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.connectors.base import FetchItem
from app.database import Base
from app.engine import CollectionEngine
from app.models import ItemTopicMembership, SourceChannel, SourceConfig, Topic


def test_cross_topic_dedup_keeps_both_topic_memberships(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'memberships.db'}")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add_all([
            SourceConfig(id="source-a", name="Source", channel=SourceChannel.WEB_SCRAPE),
            Topic(id="topic-a", name="Topic A"),
            Topic(id="topic-b", name="Topic B"),
        ])
        db.commit()
        item_a = FetchItem(
            title="同一条全球贸易风险信息",
            content="完整正文" * 80,
            url="https://example.com/trade-risk",
            published_at=datetime(2026, 8, 3, tzinfo=timezone.utc),
            language="zh",
            relevance_score=0.95,
        )
        item_b = FetchItem(**{**item_a.__dict__, "relevance_score": 0.70})
        collector = CollectionEngine(db)

        collector._persist_items([item_a], "source-a", "run-a", topic_id="topic-a")
        collector._persist_items([item_b], "source-a", "run-b", topic_id="topic-b")

        memberships = db.query(ItemTopicMembership).order_by(
            ItemTopicMembership.topic_id,
        ).all()
        assert [(row.topic_id, row.last_run_id, row.relevance_score) for row in memberships] == [
            ("topic-a", "run-a", 0.95),
            ("topic-b", "run-b", 0.70),
        ]
    finally:
        db.close()
        engine.dispose()
