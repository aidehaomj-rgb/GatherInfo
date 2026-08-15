"""Stable selection of high-value intelligence for the home page."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import CollectedItem, SystemConfig

FEATURED_LIMIT = 3
RECENT_WINDOW_DAYS = 10
MAX_CANDIDATES = 500
MIN_FEATURED_SCORE = 55.0

DOMAIN_SIGNALS = (
    ("海关监管", 22, ("中国海关", "海关监管", "通关", "申报", "查验", "稽查", "customs")),
    ("风险防控", 18, ("风险防控", "风险管理", "走私", "违规", "查获", "扣押", "risk", "smuggl")),
    ("出口管制", 18, ("出口管制", "两用物项", "制裁", "禁运", "实体清单", "export control", "sanction")),
    ("对华贸易影响", 18, ("对华贸易", "中国企业", "中国出口", "中国进口", "供应链", "china trade", "chinese compan")),
    ("贸易监管措施", 14, ("关税", "反倾销", "反补贴", "贸易救济", "原产地", "tbt", "sps", "tariff")),
)


DOMAIN_SIGNALS = (
    ("海关监管", 22, ("海关", "海关监管", "通关", "申报", "查验", "稽查", "缉私", "customs", "border force", "border protection", "cbp")),
    ("执法查发", 22, ("查获", "扣押", "没收", "逮捕", "调查", "处罚", "走私", "瞒报", "伪报", "seize", "seized", "seizure", "arrest", "detain", "detained", "smuggl", "false declaration", "enforcement")),
    ("风险防控", 18, ("风险防控", "风险管理", "违规", "异常", "risk", "violation", "compliance")),
    ("出口管制", 18, ("出口管制", "两用物项", "制裁", "禁运", "实体清单", "许可证", "export control", "dual-use", "sanction", "entity list", "license")),
    ("涉华贸易影响", 18, ("涉华", "中国企业", "中国出口", "中国进口", "中国产", "中国籍", "供应链", "china trade", "chinese company", "made in china", "china-origin")),
    ("贸易监管措施", 14, ("关税", "反倾销", "反补贴", "贸易救济", "原产地", "技术性贸易措施", "tbt", "sps", "tariff", "anti-dumping", "countervailing")),
)


@dataclass(frozen=True)
class FeaturedScore:
    score: float
    qualified: bool
    signals: tuple[str, ...]


def score_featured_item(item: CollectedItem | Any, now: datetime | None = None) -> FeaturedScore:
    now = now or datetime.now(timezone.utc)
    text = _item_text(item).casefold()
    matched = tuple(
        label for label, _, keywords in DOMAIN_SIGNALS
        if any(keyword.casefold() in text for keyword in keywords)
    )
    domain_score = sum(
        weight for label, weight, _ in DOMAIN_SIGNALS if label in matched
    )
    review = _quality_review(item)
    review_score = (
        _number(review.get("completeness_score")) * 0.10
        + _number(review.get("customs_value_score")) * 0.14
        + _number(review.get("topic_relevance_score")) * 0.06
        + _number(review.get("confidence")) * 0.04
    )
    content_score = _content_completeness_score(item)
    model_score = min(10.0, (
        float(getattr(item, "quality_score", 0) or 0)
        + float(getattr(item, "relevance_score", 0) or 0)
    ) * 5)
    recency_score = _recency_score(item, now)
    total = min(100.0, domain_score + review_score + content_score + model_score + recency_score)
    qualified_review = _enforcement_review_approved(item)
    qualified = bool(matched) and total >= MIN_FEATURED_SCORE and (content_score >= 8 or qualified_review)
    return FeaturedScore(round(total, 2), qualified, matched)


def choose_featured_ids(
    saved_ids: list[str],
    ranked: list[tuple[Any, ...]],
    *,
    available_ids: set[str],
    limit: int = FEATURED_LIMIT,
) -> list[str]:
    valid_saved = [item_id for item_id in saved_ids if item_id in available_ids]
    ranked_ids = [item_id for item_id, *_ in ranked if item_id in available_ids]
    if not ranked_ids:
        return valid_saved[:limit]

    proposed = ranked_ids[:limit]
    proposed = [*proposed, *(item_id for item_id in valid_saved if item_id not in proposed)][:limit]
    if len(valid_saved) == limit and not any(item_id not in valid_saved for item_id in proposed):
        return valid_saved
    return proposed


def get_featured_items(
    db: Session,
    *,
    now: datetime | None = None,
    limit: int = FEATURED_LIMIT,
) -> list[CollectedItem]:
    now = now or datetime.now(timezone.utc)
    config = db.query(SystemConfig).filter(SystemConfig.id == "global").first()
    created_config = config is None
    if not config:
        config = SystemConfig(id="global")
        db.add(config)
        db.flush()

    saved_ids = list(config.featured_item_ids or [])
    saved_items = _load_items(db, saved_ids)
    cutoff = now - timedelta(days=RECENT_WINDOW_DAYS)
    candidates = db.query(CollectedItem).filter(or_(
        CollectedItem.published_at >= cutoff,
        CollectedItem.published_at.is_(None) & (CollectedItem.collected_at >= cutoff),
    )).order_by(CollectedItem.collected_at.desc()).limit(MAX_CANDIDATES).all()
    ranked = [
        (
            item.id,
            result.score,
            _enforcement_review_approved(item),
            _china_relevance_rank(item),
            _item_time(item),
        )
        for item in candidates
        if (result := score_featured_item(item, now)).qualified
    ]
    ranked.sort(
        key=lambda value: (
            value[3],
            value[2],
            value[4] or datetime.min.replace(tzinfo=timezone.utc),
            value[1],
        ),
        reverse=True,
    )
    available_ids = {item.id for item in [*saved_items, *candidates]}
    selected_ids = choose_featured_ids(
        saved_ids, ranked, available_ids=available_ids, limit=limit,
    )
    if selected_ids != saved_ids:
        config.featured_item_ids = list(selected_ids)
        config.featured_updated_at = now
        db.commit()
    elif created_config:
        db.commit()
    return _load_items(db, selected_ids)


def _load_items(db: Session, item_ids: list[str]) -> list[CollectedItem]:
    if not item_ids:
        return []
    rows = db.query(CollectedItem).filter(CollectedItem.id.in_(item_ids)).all()
    row_map = {item.id: item for item in rows}
    return [row_map[item_id] for item_id in item_ids if item_id in row_map]


def _quality_review(item: CollectedItem | Any) -> dict[str, Any]:
    metadata = getattr(item, "raw_metadata", None)
    if not isinstance(metadata, dict):
        return {}
    review = metadata.get("quality_review")
    return review if isinstance(review, dict) else {}


def _enforcement_review_approved(item: CollectedItem | Any) -> bool:
    metadata = getattr(item, "raw_metadata", None)
    if not isinstance(metadata, dict):
        return False
    review = metadata.get("enforcement_review")
    return isinstance(review, dict) and str(review.get("decision") or "").lower() == "approve"


def _china_relevance_rank(item: CollectedItem | Any) -> int:
    metadata = getattr(item, "raw_metadata", None)
    if not isinstance(metadata, dict):
        return 0
    review = metadata.get("enforcement_review")
    if not isinstance(review, dict):
        return 0
    return {
        "strong": 3,
        "medium": 2,
        "weak": 1,
        "major_non_china": 0,
    }.get(str(review.get("china_relevance_level") or "").lower(), 0)


def _item_text(item: CollectedItem | Any) -> str:
    metadata = getattr(item, "raw_metadata", None)
    translation = metadata.get("translation_zh", {}) if isinstance(metadata, dict) else {}
    return " ".join(str(value or "") for value in (
        getattr(item, "title", ""), getattr(item, "summary", ""), getattr(item, "content", ""),
        translation.get("title_zh"), translation.get("summary_zh"), translation.get("content_zh"),
    ))


def _content_completeness_score(item: CollectedItem | Any) -> float:
    title = str(getattr(item, "title", "") or "").strip()
    summary = str(getattr(item, "summary", "") or "").strip()
    content = str(getattr(item, "content", "") or "").strip()
    return min(15.0, (3 if len(title) >= 8 else 0) + (4 if len(summary) >= 60 else 0) + (8 if len(content) >= 300 else 0))


def _recency_score(item: CollectedItem | Any, now: datetime) -> float:
    value = _item_time(item)
    if not isinstance(value, datetime):
        return 0.0
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (now - value).total_seconds() / 86400)
    return max(0.0, 8.0 - age_days * 0.8)


def _item_time(item: CollectedItem | Any) -> datetime | None:
    return getattr(item, "published_at", None) or getattr(item, "collected_at", None)


def _number(value: Any) -> float:
    try:
        return max(0.0, min(100.0, float(value or 0)))
    except (TypeError, ValueError):
        return 0.0
