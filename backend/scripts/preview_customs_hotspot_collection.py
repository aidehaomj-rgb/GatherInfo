"""Preview customs-risk hotspot collection without persisting items or reports."""
from __future__ import annotations

import asyncio
import json
import sys
from dataclasses import replace
from datetime import timedelta
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.connectors.base import ConnectorRegistry
from app.content_quality import curate_article_candidates
from app.database import SessionLocal
from app.engine import _filter_items_by_window, utc_now
from app.model_defaults import get_default_model
from app.models import CollectedItem, ModelConfig, Report, SourceConfig, Topic
from app.research_planner import build_research_queries


TOPIC_ID = "weekly-trade-current-affairs"
SOURCE_ID = "ai-smart-web-research"
OUTPUT_DIR = Path("data/previews/customs_hotspots")


def _model(db, topic: Topic) -> ModelConfig | None:
    if topic.ai_research_model_id:
        selected = db.query(ModelConfig).filter(
            ModelConfig.id == topic.ai_research_model_id,
            ModelConfig.is_active == True,
        ).first()
        if selected:
            return selected
    return get_default_model(db)


def _context(topic: Topic) -> dict:
    return {
        "topic_id": topic.id,
        "name": topic.name,
        "description": topic.description or "",
        "semantic_instruction": topic.description_prompt or "",
        "keywords": topic.keywords or [],
    }


def _payload(item) -> dict:
    metadata = item.raw_metadata if isinstance(item.raw_metadata, dict) else {}
    translation = metadata.get("translation_zh") if isinstance(metadata.get("translation_zh"), dict) else {}
    review = metadata.get("customs_hotspot_review") if isinstance(metadata.get("customs_hotspot_review"), dict) else {}
    return {
        "title": translation.get("title_zh") or item.title,
        "published_at": item.published_at,
        "url": item.url,
        "source_type": review.get("source_type") or "待核验",
        "facts": review.get("facts") or item.summary or (item.content or "")[:1000],
        "customs_risk": review.get("customs_risk") or "待进一步研判",
        "data_checks": review.get("data_checks") or "待进一步制定核查指标",
        "risk_level": review.get("risk_level") or "待评估",
        "china_nexus": review.get("china_nexus") or "待核验",
        "review_method": review.get("method") or "unknown",
        "summary": translation.get("summary_zh") or item.summary,
        "content_preview": (translation.get("content_zh") or item.content or "")[:1600],
        "provider": metadata.get("research_provider") or metadata.get("provider") or "unknown",
    }


def _markdown(payload: dict) -> str:
    lines = [
        "# 涉进出口时政热点采集预览",
        "",
        f"采集窗口：{payload['window_start'][:10]}至{payload['window_end'][:10]}",
        "",
        "本材料为预览结果，尚未导入GatherInfo采集条目和报告库。风险内容为待海关数据验证的研判，不代表已经发生违法行为。",
        "",
        f"候选发现：{payload['found_count']}条；时间窗口内：{payload['window_kept_count']}条；审核后预览：{payload['approved_count']}条。",
    ]
    for index, item in enumerate(payload["items"], 1):
        lines.extend([
            "", f"## {index}. {item['title']}", "",
            f"- 发布日期：{str(item['published_at'] or '待核验')[:10]}",
            f"- 来源性质：{item['source_type']}",
            f"- 检索渠道：{item['provider']}",
            f"- 风险等级：{item['risk_level']}",
            f"- 中国关联：{item['china_nexus']}",
            f"- 原文链接：{item['url'] or '无'}", "",
            f"**事实依据：** {item['facts']}", "",
            f"**海关监管风险：** {item['customs_risk']}", "",
            f"**数据核查建议：** {item['data_checks']}",
        ])
    if payload["errors"]:
        lines.extend(["", "## 采集诊断", ""])
        lines.extend(f"- {error}" for error in payload["errors"])
    return "\n".join(lines).strip() + "\n"


async def main() -> None:
    db = SessionLocal()
    try:
        topic = db.query(Topic).filter(Topic.id == TOPIC_ID).first()
        source = db.query(SourceConfig).filter(SourceConfig.id == SOURCE_ID).first()
        if not topic or not source:
            raise SystemExit("Required topic or aggregate research source is missing")
        before_items = db.query(CollectedItem).filter(CollectedItem.topic_id == TOPIC_ID).count()
        before_reports = db.query(Report).filter(Report.topic_id == TOPIC_ID).count()

        window_days = int(topic.collect_window_days or 20)
        window_end = utc_now()
        window_start = (window_end - timedelta(days=window_days)).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        model = _model(db, topic)
        queries = await build_research_queries(
            topic, topic.description_prompt or "", model,
            max_queries=12, window_days=window_days,
        )

        # Use a detached configuration clone so preview-specific breadth never
        # changes the persisted source configuration.
        config = replace_source_config(source)
        connector = ConnectorRegistry.create(config)
        connector.set_collection_window(window_start, window_end)
        result = await connector.fetch(queries, max_items=60)
        window_items, window_rejected = _filter_items_by_window(
            result.items, window_start, window_end,
        )

        deduped = []
        seen = set()
        for item in window_items:
            key = (item.url or item.title or "").strip().casefold()
            if not key or key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        approved, rejected = await curate_article_candidates(
            deduped[:30], model, _context(topic),
        )
        items = [_payload(item) for item in approved]
        errors = list(result.error_log or [])
        if window_rejected:
            errors.append(f"时间窗口过滤{window_rejected}条：发布日期缺失或超出20天范围")
        if rejected:
            reasons = {}
            for entry in rejected:
                reasons[entry.reason] = reasons.get(entry.reason, 0) + 1
            errors.extend(f"审核过滤{count}条：{reason}" for reason, count in reasons.items())

        after_items = db.query(CollectedItem).filter(CollectedItem.topic_id == TOPIC_ID).count()
        after_reports = db.query(Report).filter(Report.topic_id == TOPIC_ID).count()
        payload = {
            "mode": "preview_only_not_persisted",
            "topic_id": topic.id,
            "topic_name": topic.name,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "queries": queries,
            "found_count": len(result.items),
            "window_kept_count": len(deduped),
            "approved_count": len(items),
            "items": items,
            "errors": errors,
            "persistence_check": {
                "items_before": before_items, "items_after": after_items,
                "reports_before": before_reports, "reports_after": after_reports,
                "unchanged": before_items == after_items and before_reports == after_reports,
            },
        }
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        json_path = OUTPUT_DIR / "latest_preview.json"
        md_path = OUTPUT_DIR / "latest_preview.md"
        json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        md_path.write_text(_markdown(payload), encoding="utf-8")
        print(json.dumps({
            "json": str(json_path), "markdown": str(md_path),
            "found": payload["found_count"], "window_kept": payload["window_kept_count"],
            "approved": payload["approved_count"],
            "persistence_check": payload["persistence_check"],
        }, ensure_ascii=False, indent=2))
    finally:
        db.rollback()
        db.close()


def replace_source_config(source: SourceConfig):
    """Build a connector-compatible copy without attaching it to the session."""
    from types import SimpleNamespace

    auth_config = dict(source.auth_config or {})
    auth_config.update({
        "include_raw_content": True,
        "resolve_published_dates": True,
        "max_date_resolutions": 40,
        "max_queries": 12,
    })
    return SimpleNamespace(
        id=source.id, name=source.name, channel=source.channel,
        api_key=source.api_key, api_key_ref=source.api_key_ref,
        base_url=source.base_url, api_endpoint=source.api_endpoint,
        auth_config=auth_config, default_keywords=source.default_keywords,
        default_categories=source.default_categories,
        timeout_seconds=source.timeout_seconds, rate_limit_rps=source.rate_limit_rps,
        max_items_per_run=max(int(source.max_items_per_run or 0), 60),
    )


if __name__ == "__main__":
    asyncio.run(main())
