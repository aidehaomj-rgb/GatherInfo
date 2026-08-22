import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.connectors.base import CollectResult, FetchItem
from app.database import Base
from app.engine import CollectionEngine
from app.models import (
    CollectionBatch, JobStatus, SourceChannel, SourceConfig, Topic,
)


def _db():
    sql_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(sql_engine)
    return sql_engine, sessionmaker(bind=sql_engine)()


def _seed(db):
    db.add(Topic(
        id="global-trade", name="关税类贸易政策", keywords=["tariff"],
        source_ids=["official-source", "blocked-source"], collect_window_days=30,
    ))
    db.add_all([
        SourceConfig(
            id="official-source", name="Official", channel=SourceChannel.WEB_SCRAPE,
            base_url="https://example.gov/news", is_active=True, is_configured=True,
            verification_status="verified", robots_status="allowed",
            terms_status="public_domain", llm_ingest_allowed=True,
            collection_profile={"pool": "core"},
        ),
        SourceConfig(
            id="blocked-source", name="Blocked", channel=SourceChannel.WEB_SCRAPE,
            base_url="https://blocked.example/news", is_active=True, is_configured=True,
            verification_status="imported_unverified", robots_status="unverified",
            terms_status="unverified", llm_ingest_allowed=False,
        ),
    ])
    db.commit()


def test_optimized_topic_runs_at_most_two_rounds_and_persists_acceptance():
    sql_engine, db = _db()
    try:
        _seed(db)
        engine = CollectionEngine(db)
        engine._collect_topic_round = AsyncMock(side_effect=[
            [CollectResult("run-1", "official-source", JobStatus.COMPLETED,
                           [FetchItem(title="first", url="https://a.test/1")])],
            [CollectResult("run-2", "official-source", JobStatus.COMPLETED,
                           [FetchItem(title="second", url="https://b.test/2")])],
        ])

        results = asyncio.run(engine.collect_topic("global-trade"))

        batch = db.query(CollectionBatch).one()
        assert len(results) == 2
        assert engine._collect_topic_round.await_count == 2
        assert batch.current_round == 2
        assert batch.status == "completed"
        assert batch.stop_reason == "max_rounds_reached"
        assert len(batch.round_summaries) == 2
        assert batch.target["target_items"] >= 15
        assert batch.gaps
        assert batch.source_plan["source_pool_size"] == 2
        assert batch.source_plan["eligible_source_count"] == 1
        assert batch.source_plan["blocked_source_count"] == 1
        blocked = next(
            row for row in batch.source_plan["collection_plan"]
            if row["source_id"] == "blocked-source"
        )
        assert blocked["automated_fetch_allowed"] is False
        assert "尚未核验" in blocked["block_reason"]
        assert batch.round_summaries[0]["search_runs"]
        assert batch.round_summaries[0]["coverage_audit"]
    finally:
        db.close()
        sql_engine.dispose()


def test_optimized_topic_stops_when_a_round_finds_no_new_urls():
    sql_engine, db = _db()
    try:
        _seed(db)
        engine = CollectionEngine(db)
        engine._collect_topic_round = AsyncMock(return_value=[
            CollectResult("run-1", "official-source", JobStatus.COMPLETED, []),
        ])

        asyncio.run(engine.collect_topic("global-trade"))

        batch = db.query(CollectionBatch).one()
        assert engine._collect_topic_round.await_count == 1
        assert batch.stop_reason == "no_new_urls"
    finally:
        db.close()
        sql_engine.dispose()


def test_rejected_discovered_urls_still_trigger_the_followup_round():
    sql_engine, db = _db()
    try:
        _seed(db)
        engine = CollectionEngine(db)
        engine._collect_topic_round = AsyncMock(side_effect=[
            [CollectResult(
                "run-1", "official-source", JobStatus.COMPLETED, [],
                items_discovered=1,
                discovered_urls=("https://example.gov/rejected-but-real",),
                items_quality_rejected=1,
            )],
            [CollectResult("run-2", "official-source", JobStatus.COMPLETED, [])],
        ])

        asyncio.run(engine.collect_topic("global-trade"))

        batch = db.query(CollectionBatch).one()
        assert engine._collect_topic_round.await_count == 2
        assert batch.round_summaries[0]["new_urls_seen"] == 1
        assert batch.stop_reason == "no_new_urls"
    finally:
        db.close()
        sql_engine.dispose()
