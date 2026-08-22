"""Batch-level measurements for the bounded topic collection loop."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from app.collection_strategy import compute_dynamic_target, evaluate_batch_metrics
from app.models import CollectedItem
from app.services.topic_item_query import filter_items_by_topic
from app.topic_research_context import TopicResearchContext


BEIJING = ZoneInfo("Asia/Shanghai")


def weekly_counts(
    db: Session,
    topic_id: str,
    *,
    now: datetime | None = None,
    weeks: int = 8,
) -> list[int]:
    """Count formal items in the most recent complete Beijing calendar weeks."""
    current = _aware(now or datetime.now(timezone.utc)).astimezone(BEIJING)
    this_monday = (current - timedelta(days=current.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    first_monday = this_monday - timedelta(weeks=weeks)
    query = filter_items_by_topic(db.query(CollectedItem), topic_id).filter(
        CollectedItem.collected_at >= first_monday.astimezone(timezone.utc),
        CollectedItem.collected_at < this_monday.astimezone(timezone.utc),
    )
    counts = [0 for _ in range(weeks)]
    for item in query.all():
        collected = _aware(item.collected_at).astimezone(BEIJING)
        index = int((collected - first_monday).days // 7)
        if 0 <= index < weeks:
            counts[index] += 1
    return counts


def dynamic_policy(
    db: Session,
    context: TopicResearchContext,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Resolve the weekly target and coverage thresholds for one batch."""
    minimum, maximum = context.policy.weekly_target
    target = compute_dynamic_target(
        weekly_counts(db, context.topic_id, now=now), minimum, maximum,
    )
    default_top_ratio = 0.4 if context.topic_id == "foreign-trade-forum-risk-monitoring" else 0.6
    max_top_ratio = context.policy.max_top_source_ratio or default_top_ratio
    required_fields = {
        "item-56adc0": ["information_type", "facts"],
        "global-trade": ["policy_stage", "facts"],
        "foreign-trade-forum-risk-monitoring": ["evidence_notice", "goods|route|actors|countries"],
        "weekly-enforcement-intelligence": ["authority", "case_number|goods|route"],
        "tech-regulations": ["measure_stage", "goods|products"],
        "weekly-trade-current-affairs": ["information_type", "facts", "analysis_judgement", "analysis_basis"],
    }.get(context.topic_id, [])
    return {
        "target_items": target,
        "target_range": [minimum, maximum],
        "min_domains": context.policy.minimum_domains,
        "min_regions": context.policy.minimum_regions,
        "min_high_evidence_ratio": context.policy.minimum_preferred_evidence_ratio,
        "high_evidence_grades": list(context.policy.preferred_evidence_grades),
        "max_top_source_ratio": max_top_ratio,
        "minimum_quality": context.policy.minimum_quality,
        "minimum_relevance": context.policy.minimum_relevance,
        "required_structure_fields": required_fields,
        "min_structure_ratio": 0.7,
    }


def current_week_records(
    db: Session,
    topic_id: str,
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return detached evidence records used by batch acceptance."""
    current = _aware(now or datetime.now(timezone.utc)).astimezone(BEIJING)
    monday = (current - timedelta(days=current.weekday())).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    query = filter_items_by_topic(db.query(CollectedItem), topic_id).filter(
        CollectedItem.collected_at >= monday.astimezone(timezone.utc),
    )
    return [_acceptance_record(item) for item in query.all()]


def evaluate_topic_batch(
    db: Session,
    context: TopicResearchContext,
    policy: dict[str, Any],
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    return evaluate_batch_metrics(
        current_week_records(db, context.topic_id, now=now), policy,
    )


def structured_gaps(acceptance: dict[str, Any]) -> list[dict[str, Any]]:
    """Turn check keys into stable operator-facing causes and follow-up lanes."""
    labels = {
        "items": ("事件量不足或有效候选未通过", "补充低覆盖政策工具、商品和最新事件"),
        "domains": ("独立来源覆盖不足", "补充官方原文和不同域名的独立报道"),
        "regions": ("来源或地域集中", "补充缺少的国家、市场和司法辖区"),
        "evidence_ratio": ("高等级证据不足", "优先查找政府、法院和国际组织原文"),
        "source_concentration": ("单一来源占比过高", "改用其他专业来源和官方材料交叉核验"),
        "structure": ("主题关键事实字段覆盖不足", "补充政策阶段、主体、商品、路线、案号或分析依据"),
        "formal_completeness": ("正式信息的日期或原文链接不完整", "回溯原始页面并核验发布日期与稳定URL"),
    }
    return [
        {"code": code, "reason": labels.get(code, (code, code))[0],
         "follow_up": labels.get(code, (code, code))[1]}
        for code in acceptance.get("gaps", [])
    ]


def _acceptance_record(item: CollectedItem) -> dict[str, Any]:
    metadata = item.raw_metadata if isinstance(item.raw_metadata, dict) else {}
    review = metadata.get("quality_review") if isinstance(metadata.get("quality_review"), dict) else {}
    assessment = metadata.get("trade_assessment") if isinstance(metadata.get("trade_assessment"), dict) else {}
    profile = metadata.get("intelligence_profile") if isinstance(metadata.get("intelligence_profile"), dict) else {}
    enforcement = metadata.get("enforcement_review") if isinstance(metadata.get("enforcement_review"), dict) else {}
    host = urlparse(item.url or "").netloc.casefold()
    countries = profile.get("countries") if isinstance(profile.get("countries"), list) else []
    jurisdiction = enforcement.get("jurisdiction") or (countries[0] if countries else "")
    return {
        "source_host": host,
        "jurisdiction": jurisdiction,
        "evidence_grade": assessment.get("evidence_grade") or enforcement.get("evidence_grade") or "",
        "url": item.url,
        "published_at": item.published_at.isoformat() if item.published_at else None,
        "information_type": assessment.get("information_type"),
        "facts": assessment.get("facts") or enforcement.get("facts"),
        "analysis_judgement": assessment.get("analysis_judgement"),
        "analysis_basis": assessment.get("analysis_basis"),
        "policy_stage": assessment.get("policy_stage"),
        "measure_stage": assessment.get("measure_stage"),
        "authority": assessment.get("authority") or enforcement.get("authority"),
        "case_number": assessment.get("case_number") or enforcement.get("case_number"),
        "goods": assessment.get("goods"),
        "route": assessment.get("route"),
        "products": profile.get("products"),
        "actors": profile.get("actors"),
        "countries": countries,
        "evidence_notice": assessment.get("evidence_notice"),
    }


def _aware(value: datetime | None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


__all__ = [
    "current_week_records", "dynamic_policy", "evaluate_topic_batch",
    "structured_gaps", "weekly_counts",
]
