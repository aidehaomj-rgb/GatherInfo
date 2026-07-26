"""Run every active topic sequentially for an unattended collection window.

The queue deliberately creates a fresh SQLAlchemy session for each topic. That
keeps long LLM-assisted collection work from holding stale ORM objects and
lets operators inspect progress through the normal ``collection_runs`` table.
"""
from __future__ import annotations

import asyncio
import argparse
import json
import logging
from pathlib import Path
import sys
from datetime import datetime, timezone

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal, init_db
from app.engine import CollectionEngine
from app.models import CollectionRun, JobStatus, Topic


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("topic_queue")
POLL_SECONDS = 15


def active_topic_ids(only_original: bool, skip_ids: set[str]) -> list[str]:
    db = SessionLocal()
    try:
        topics = db.query(Topic).filter(Topic.is_active == True).all()
        if only_original:
            topics = [topic for topic in topics if not topic.id.startswith("nightly-")]
        topics = [topic for topic in topics if topic.id not in skip_ids]
        return [topic.id for topic in sorted(topics, key=lambda value: (not value.id.startswith("nightly-"), value.created_at or datetime.min))]
    finally:
        db.close()


def topic_is_running(topic_id: str) -> bool:
    db = SessionLocal()
    try:
        return db.query(CollectionRun).filter(
            CollectionRun.topic_id == topic_id,
            CollectionRun.status.in_([JobStatus.PENDING, JobStatus.RUNNING]),
        ).first() is not None
    finally:
        db.close()


async def wait_until_idle(topic_id: str) -> None:
    while topic_is_running(topic_id):
        logger.info("topic=%s has an existing run; waiting", topic_id)
        await asyncio.sleep(POLL_SECONDS)


async def collect_topic(topic_id: str) -> None:
    await wait_until_idle(topic_id)
    db = SessionLocal()
    started = datetime.now(timezone.utc)
    try:
        result = await CollectionEngine(db).collect_topic(topic_id)
        summary = {
            "topic_id": topic_id,
            "started_at": started.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "sources": len(result),
            "items_new": sum(item.items_new for item in result),
            "failed_sources": sum(1 for item in result if item.status == JobStatus.FAILED),
        }
        logger.info("TOPIC_RESULT %s", json.dumps(summary, ensure_ascii=False))
    except Exception:
        logger.exception("TOPIC_ERROR topic=%s", topic_id)
    finally:
        db.close()


async def main(only_original: bool, skip_ids: set[str]) -> None:
    init_db()
    topic_ids = active_topic_ids(only_original, skip_ids)
    logger.info("starting unattended queue for %d active topics", len(topic_ids))
    for topic_id in topic_ids:
        await collect_topic(topic_id)
    logger.info("unattended queue completed")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run active collection topics sequentially")
    parser.add_argument("--only-original", action="store_true", help="skip auto-created nightly topics")
    parser.add_argument("--skip-topic", action="append", default=[], help="topic ID to skip")
    args = parser.parse_args()
    asyncio.run(main(args.only_original, set(args.skip_topic)))
