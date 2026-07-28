"""Regression tests for current persisted-item inventory counts."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal  # noqa: E402
from app.main import _rate_limit_store, create_app  # noqa: E402
from app.models import CollectedItem, CollectionRun, Topic  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402


client = TestClient(create_app())


def test_inventory_and_topic_out_use_current_items() -> None:
    source_id = "inventory-regression-source"
    topic_id = "inventory-regression-topic"
    run_id = "inventory-regression-run"
    item_id = "inventory-regression-item"

    source = client.post("/api/v1/sources", json={
        "id": source_id, "name": "Inventory Regression Source", "channel": "rss",
        "base_url": "https://example.com/feed.xml",
    })
    assert source.status_code in (200, 201)
    topic = client.post("/api/v1/topics", json={
        "id": topic_id, "name": "Inventory Regression Topic", "keywords": ["inventory"],
    })
    assert topic.status_code in (200, 201)

    db = SessionLocal()
    try:
        stored_topic = db.get(Topic, topic_id)
        assert stored_topic is not None
        stored_topic.total_items_collected = 7000
        db.add(CollectionRun(
            id=run_id, source_id=source_id, topic_id=topic_id,
            batch_id="inventory-regression-batch", status="completed",
            items_found=7000, items_new=1,
        ))
        db.add(CollectedItem(
            id=item_id, source_id=source_id, topic_id=topic_id, run_id=run_id,
            title="Current persisted item", content="A complete item.",
        ))
        db.commit()

        topic_body = client.get(f"/api/v1/topics/{topic_id}").json()
        assert topic_body["total_items_collected"] == 7000
        assert topic_body["current_item_count"] == 1

        inventory_response = client.get("/api/v1/items/inventory")
        assert inventory_response.status_code == 200
        inventory = inventory_response.json()
        assert next(row for row in inventory["topics"] if row["id"] == topic_id)["count"] == 1
        assert next(row for row in inventory["batches"] if row["id"] == "inventory-regression-batch")["count"] == 1
    finally:
        db.query(CollectedItem).filter(CollectedItem.id == item_id).delete(synchronize_session=False)
        db.query(CollectionRun).filter(CollectionRun.id == run_id).delete(synchronize_session=False)
        db.query(Topic).filter(Topic.id == topic_id).delete(synchronize_session=False)
        db.commit()
        db.close()
        _rate_limit_store.clear()
        client.delete(f"/api/v1/sources/{source_id}")
