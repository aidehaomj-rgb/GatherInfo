"""Topic-scoped reads must include globally deduplicated membership items."""
from datetime import datetime, timezone
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base
from app.connectors.base import FetchItem
from app.engine import CollectionEngine
from app.models import (
    CollectedItem,
    ItemTopicMembership,
    SourceChannel,
    SourceConfig,
    Topic,
)
from app.routes.items import item_inventory
from app.routes.haisee import _resolve_items as resolve_haisee_items
from app.routes.material_sets import MaterialSetCreate, _resolve_create_scope
from app.routes.ymg_deep import _resolve_items as resolve_ymg_items
from app.services.item_service import build_item_query, get_item_ids
from app.stats_routes import dashboard


def _session() -> Session:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return Session(engine)


def _seed_membership_item(db: Session) -> None:
    now = datetime.now(timezone.utc)
    db.add_all([
        SourceConfig(
            id="source", name="Source", channel=SourceChannel.RSS,
        ),
        Topic(id="topic-a", name="Topic A", keywords=["a"]),
        Topic(id="topic-b", name="Topic B", keywords=["b"]),
        CollectedItem(
            id="shared", source_id="source", topic_id="topic-a",
            title="Shared intelligence", content="Complete evidence body",
            published_at=now, collected_at=now,
        ),
    ])
    db.commit()
    db.add_all([
        ItemTopicMembership(item_id="shared", topic_id="topic-a"),
        ItemTopicMembership(item_id="shared", topic_id="topic-b"),
    ])
    db.commit()


def test_item_service_topic_filter_includes_membership_without_duplicates() -> None:
    db = _session()
    try:
        _seed_membership_item(db)

        assert [row.id for row in build_item_query(db, topic_id="topic-b").all()] == ["shared"]
        ids, total = get_item_ids(db, topic_id="topic-a")
        assert ids == ["shared"]
        assert total == 1
    finally:
        db.close()


def test_material_set_and_ymg_topic_scope_include_membership_items() -> None:
    db = _session()
    try:
        _seed_membership_item(db)

        items, topic_id, source_type, _ = _resolve_create_scope(
            db, MaterialSetCreate(topic_id="topic-b"),
        )
        ymg_items = resolve_ymg_items(db, "topic-b", None, None)
        haisee_items = resolve_haisee_items(db, [], topic_id="topic-b")

        assert [item.id for item in items] == ["shared"]
        assert topic_id == "topic-b"
        assert source_type == "topic"
        assert [item.id for item in ymg_items] == ["shared"]
        assert [item.id for item in haisee_items] == ["shared"]
    finally:
        db.close()


def test_inventory_and_dashboard_count_membership_for_each_topic_once() -> None:
    db = _session()
    try:
        _seed_membership_item(db)

        inventory = item_inventory(db)
        inventory_counts = {row.id: row.count for row in inventory.topics}
        stats = dashboard(db)
        dashboard_counts = {
            row["topic_id"]: row["item_count"] for row in stats["topic_stats"]
        }

        assert inventory_counts["topic-a"] == 1
        assert inventory_counts["topic-b"] == 1
        assert dashboard_counts["topic-a"] == 1
        assert dashboard_counts["topic-b"] == 1
    finally:
        db.close()


def test_enforcement_portfolio_sees_items_attached_by_membership() -> None:
    db = _session()
    try:
        _seed_membership_item(db)
        db.add(Topic(
            id="weekly-enforcement-intelligence",
            name="执法信息采集",
            keywords=["seizure"],
        ))
        db.add(ItemTopicMembership(
            item_id="shared", topic_id="weekly-enforcement-intelligence",
        ))
        stored = db.get(CollectedItem, "shared")
        stored.url = "https://example.gov/case-1"
        db.commit()

        selected, skipped = CollectionEngine(db)._select_enforcement_portfolio([
            FetchItem(
                title="CBP seizes shipment from China",
                content="CBP seized restricted goods shipped from China.",
                url="https://example.gov/case-1",
                relevance_score=0.9,
                raw_metadata={"search_jurisdiction": "United States"},
            ),
        ], None)

        assert selected == []
        assert skipped == 1
    finally:
        db.close()
