"""Preview weekly enforcement collection without persisting items.

This follows the enforcement topic's current source bindings and review gate,
but stops before database insertion so users can inspect approved candidates.
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict
from datetime import timedelta
from pathlib import Path

from app.connectors.base import ConnectorRegistry, FetchItem
from app.database import SessionLocal
from app.engine import (
    CollectionEngine,
    MAX_ENFORCEMENT_CANDIDATES_PER_SOURCE,
    MAX_ENFORCEMENT_SEARCH_RESULTS_PER_SOURCE,
    SEMANTIC_SEARCH_CHANNELS,
    _channel_value,
    _filter_items_by_window,
    _topic_collection_keywords,
    utc_now,
)
from app.enforcement_review import (
    prioritize_enforcement_candidates,
    review_enforcement_candidates,
)
from app.model_defaults import get_default_model
from app.models import ModelConfig, SourceConfig, Topic
from app.research_planner import build_research_queries


TOPIC_ID = "weekly-enforcement-intelligence"
DEFAULT_OUTPUT = Path("data/previews/enforcement_collection_preview.json")


def _pick_model(db, topic: Topic) -> ModelConfig | None:
    selected_model_ids = (
        topic.collection_model_ids
        if isinstance(topic.collection_model_ids, list)
        else []
    )
    if selected_model_ids:
        model = db.query(ModelConfig).filter(
            ModelConfig.id.in_(selected_model_ids),
            ModelConfig.is_active == True,
        ).first()
        if model:
            return model
    if topic.ai_research_model_id:
        model = db.query(ModelConfig).filter(
            ModelConfig.id == topic.ai_research_model_id,
            ModelConfig.is_active == True,
        ).first()
        if model:
            return model
    return get_default_model(db)


def _item_payload(item: FetchItem, source: SourceConfig) -> dict:
    metadata = item.raw_metadata if isinstance(item.raw_metadata, dict) else {}
    review = metadata.get("enforcement_review") if isinstance(metadata, dict) else {}
    return {
        "title": item.title,
        "url": item.url,
        "source_id": source.id,
        "source_name": source.name,
        "published_at": item.published_at,
        "language": item.language,
        "summary": item.summary,
        "content_preview": (item.content or "")[:800],
        "review": review if isinstance(review, dict) else {},
        "raw_metadata": metadata,
    }


async def _preview_source(
    db,
    engine: CollectionEngine,
    topic: Topic,
    source: SourceConfig,
    keywords: list[str],
    window_start,
    window_end,
    model: ModelConfig | None,
) -> dict:
    channel = _channel_value(source)
    query_keywords = keywords
    if channel in SEMANTIC_SEARCH_CHANNELS:
        try:
            query_keywords = await build_research_queries(
                topic,
                topic.description_prompt or "",
                model,
                max_queries=40,
                window_days=getattr(topic, "collect_window_days", None) or 30,
            ) or keywords
        except Exception as exc:
            query_keywords = keywords
            planning_error = str(exc)
        else:
            planning_error = None
    else:
        planning_error = None

    try:
        connector = ConnectorRegistry.create(source)
        connector.set_collection_window(window_start, window_end)
        result = await connector.fetch(
            query_keywords,
            max_items=(
                MAX_ENFORCEMENT_SEARCH_RESULTS_PER_SOURCE
                if channel in SEMANTIC_SEARCH_CHANNELS
                else source.max_items_per_run
            ),
        )
    except Exception as exc:
        return {
            "source_id": source.id,
            "source_name": source.name,
            "status": "failed",
            "errors": [str(exc)],
            "found": 0,
            "window_kept": 0,
            "approved": 0,
            "items": [],
        }

    window_items, window_rejected = _filter_items_by_window(
        result.items, window_start, window_end,
    )
    window_items, existing_skipped = engine._exclude_existing_enforcement_candidates(
        window_items
    )
    retained = prioritize_enforcement_candidates(
        window_items,
        MAX_ENFORCEMENT_CANDIDATES_PER_SOURCE,
        existing_counts=engine._enforcement_jurisdiction_counts(window_start),
    )
    approved = await review_enforcement_candidates(retained, model)

    errors = list(result.error_log or [])
    if planning_error:
        errors.append(f"AI 检索式生成失败，已回退关键词：{planning_error}")

    return {
        "source_id": source.id,
        "source_name": source.name,
        "status": "completed",
        "errors": errors,
        "found": len(result.items),
        "window_rejected": window_rejected,
        "existing_skipped": existing_skipped,
        "window_kept": len(window_items),
        "reviewed": len(retained),
        "approved": len(approved),
        "items": [_item_payload(item, source) for item in approved],
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", action="append", dest="sources")
    parser.add_argument("--limit-sources", type=int, default=0)
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT))
    args = parser.parse_args()

    db = SessionLocal()
    try:
        topic = db.query(Topic).filter(Topic.id == TOPIC_ID).first()
        if not topic:
            raise SystemExit(f"Topic not found: {TOPIC_ID}")
        engine = CollectionEngine(db)
        sources = engine._resolve_sources(topic)
        if args.sources:
            allowed = set(args.sources)
            sources = [source for source in sources if source.id in allowed]
        if args.limit_sources > 0:
            sources = sources[: args.limit_sources]

        window_days = getattr(topic, "collect_window_days", None) or 30
        window_end = utc_now()
        window_start = (window_end - timedelta(days=window_days)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        keywords = _topic_collection_keywords(topic)
        model = _pick_model(db, topic)

        source_results = []
        for source in sources:
            source_results.append(
                await _preview_source(
                    db, engine, topic, source, keywords, window_start, window_end, model
                )
            )

        items = [
            item
            for source_result in source_results
            for item in source_result.get("items", [])
        ]
        payload = {
            "topic_id": topic.id,
            "topic_name": topic.name,
            "mode": "preview_only_not_persisted",
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "model_id": model.id if model else None,
            "source_count": len(sources),
            "approved_count": len(items),
            "sources": source_results,
            "items": items,
        }

        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({
            "output": str(output),
            "topic": topic.name,
            "source_count": len(sources),
            "approved_count": len(items),
            "sources": [
                {
                    "id": source_result["source_id"],
                    "name": source_result["source_name"],
                    "found": source_result["found"],
                    "approved": source_result["approved"],
                    "errors": source_result["errors"][:3],
                }
                for source_result in source_results
            ],
        }, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
