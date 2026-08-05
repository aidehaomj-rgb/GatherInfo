"""Read-only connector canary for the evidence-reviewed official-source catalog."""
from __future__ import annotations

import argparse
import asyncio

import app.connectors  # noqa: F401 - register connector classes
from app.connectors.base import ConnectorRegistry
from app.database import SessionLocal
from app.engine import _topic_collection_window
from app.models import SourceConfig, Topic
from app.verified_source_catalog import CATALOG_SOURCE_IDS


async def _run(max_items: int, topic_id: str) -> int:
    db = SessionLocal()
    try:
        topic = db.get(Topic, topic_id)
        window_start, window_end = (
            _topic_collection_window(topic) if topic else (None, None)
        )
        print(
            f"window={window_start.isoformat() if window_start else '-'}.."
            f"{window_end.isoformat() if window_end else '-'}"
        )
        for source_id in CATALOG_SOURCE_IDS:
            source = db.get(SourceConfig, source_id)
            if source is None:
                print(f"{source_id}: missing")
                continue
            connector = ConnectorRegistry.create(source)
            connector.set_collection_window(window_start, window_end)
            result = await connector.fetch(
                source.default_keywords or [], max_items=max_items,
            )
            print(
                f"{source_id}: status={result.status} items={len(result.items)} "
                f"errors={result.error_log or []}"
            )
            for item in result.items[:3]:
                print(
                    f"  {item.published_at or '-'} | {item.language or '-'} | "
                    f"chars={len(item.content or '')} | {item.title[:100]}"
                )
    finally:
        db.close()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-items", type=int, default=8)
    parser.add_argument("--topic-id", default="global-trade")
    args = parser.parse_args()
    return asyncio.run(_run(max(1, min(args.max_items, 40)), args.topic_id))


if __name__ == "__main__":
    raise SystemExit(main())
