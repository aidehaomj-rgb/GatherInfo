"""Deterministic weekly intelligence selection and two-volume planning.

This module intentionally stops at a report *plan*.  The plan contains exact item
IDs and JSON-compatible ``Report`` metadata so a caller can hand each volume to
the configured LLM without letting the model decide which evidence is included.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_
from sqlalchemy.orm import Session, joinedload

from app.collection_policy import evaluate_collection_policy
from app.language_quality import is_substantially_chinese
from app.models import CollectedItem, ItemTopicMembership, Report, SourceConfig, Topic


BEIJING = ZoneInfo("Asia/Shanghai")
UTC = timezone.utc
_PUBLICATION_LOCKS: dict[tuple[str, str], asyncio.Lock] = {}
_COUNTRY_COVERAGE_ALIASES = {
    "美国": "US", "united states": "US",
    "澳大利亚": "AU", "australia": "AU",
    "巴西": "BR", "brazil": "BR",
    "英国": "GB", "united kingdom": "GB",
    "欧盟": "EU", "european union": "EU",
    "新西兰": "NZ", "new zealand": "NZ",
    "全球": "GLOBAL", "global": "GLOBAL",
}
_LANGUAGE_COVERAGE_ALIASES = {
    "英文": "en", "英语": "en", "english": "en",
    "中文": "zh", "汉语": "zh", "chinese": "zh",
    "葡萄牙语": "pt", "portuguese": "pt",
    "西班牙语": "es", "spanish": "es",
}


@dataclass(frozen=True)
class WeeklySelectionPolicy:
    """Selection thresholds and deterministic score weights."""

    target_items: int = 80
    minimum_items: int = 60
    minimum_part_items: int = 30
    maximum_part_items: int = 40
    minimum_content_chars: int = 180
    minimum_quality: float = 0.70
    minimum_relevance: float = 0.70
    minimum_publishability: int = 70
    maximum_source_share: float = 0.20
    minimum_sources_per_part: int = 5
    quality_weight: float = 0.45
    relevance_weight: float = 0.40
    recency_weight: float = 0.15
    source_diversity_weight: float = 0.12
    category_diversity_weight: float = 0.08
    country_diversity_weight: float = 0.06

    def __post_init__(self) -> None:
        if self.minimum_items < self.minimum_part_items * 2:
            raise ValueError("minimum_items cannot produce two valid volumes")
        if self.target_items > self.maximum_part_items * 2:
            raise ValueError("target_items exceeds the two-volume maximum")
        if self.target_items < self.minimum_items:
            raise ValueError("target_items must be at least minimum_items")
        if self.minimum_content_chars < 1:
            raise ValueError("minimum_content_chars must be positive")
        if not 0 < self.maximum_source_share <= 1:
            raise ValueError("maximum_source_share must be within (0, 1]")

    def as_dict(self) -> dict[str, int | float]:
        return asdict(self)


@dataclass(frozen=True)
class BeijingWeekWindow:
    period_key: str
    start_utc: datetime
    end_utc: datetime

    def as_dict(self) -> dict[str, str]:
        return {
            "period_key": self.period_key,
            "timezone": "Asia/Shanghai",
            "start_inclusive": self.start_utc.isoformat(),
            "end_exclusive": self.end_utc.isoformat(),
        }


@dataclass(frozen=True)
class WeeklyReportPart:
    series_id: str
    period_key: str
    part_index: int
    part_total: int
    item_ids: tuple[str, ...]

    def report_fields(
        self,
        selection_policy: dict[str, int | float],
        selection_audit: dict[str, Any],
    ) -> dict[str, Any]:
        """Return fields compatible with the extended ``Report`` model."""
        return {
            "series_id": self.series_id,
            "period_key": self.period_key,
            "part_index": self.part_index,
            "part_total": self.part_total,
            "item_ids": list(self.item_ids),
            "item_count": len(self.item_ids),
            "selection_policy": {**selection_policy},
            "selection_audit": {**selection_audit},
        }


@dataclass(frozen=True)
class WeeklyReportPlan:
    topic_id: str
    series_id: str
    period_key: str
    window: BeijingWeekWindow
    ranked_ids: tuple[str, ...]
    parts: tuple[WeeklyReportPart, ...]
    ready: bool
    minimum_shortfall: int
    target_shortfall: int
    selection_policy: dict[str, int | float]
    selection_audit: dict[str, Any]


@dataclass(frozen=True)
class WeeklyPublicationResult:
    plan: WeeklyReportPlan
    reports: tuple[Report, ...]
    reused: bool
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class _Candidate:
    item_id: str
    published_at: datetime
    source: str
    category: str
    countries: tuple[str, ...]
    quality: float
    relevance: float
    recency: float
    base_score: float


@dataclass(frozen=True)
class _TopicItemView:
    """Immutable ORM view with relevance scoped to the requested topic."""

    item: CollectedItem
    relevance_score: float

    def __getattr__(self, name: str) -> Any:
        return getattr(self.item, name)


def beijing_week_window(
    reference: datetime | date | None = None,
) -> BeijingWeekWindow:
    """Return the Beijing ISO week as an inclusive/exclusive UTC interval."""
    local_reference = _beijing_reference(reference)
    monday = local_reference.date() - timedelta(days=local_reference.weekday())
    start_local = datetime.combine(monday, time.min, tzinfo=BEIJING)
    end_local = start_local + timedelta(days=7)
    iso_year, iso_week, _ = monday.isocalendar()
    return BeijingWeekWindow(
        period_key=f"{iso_year}-W{iso_week:02d}",
        start_utc=start_local.astimezone(UTC),
        end_utc=end_local.astimezone(UTC),
    )


def select_weekly_items(
    topic_id: str,
    items: Iterable[Any],
    *,
    reference: datetime | date | None = None,
    policy: WeeklySelectionPolicy | None = None,
) -> WeeklyReportPlan:
    """Filter, rank and split weekly candidates without mutating input objects."""
    effective_policy = policy or WeeklySelectionPolicy()
    window = beijing_week_window(reference)
    ordered_items = tuple(sorted(items, key=lambda item: str(_get(item, "id") or "")))
    candidates, rejected = _filter_candidates(ordered_items, window, effective_policy)
    ranked, ranking_audit = _rank_candidates(candidates, effective_policy)
    if len(ranked) >= effective_policy.minimum_items:
        groups = _allocate_volume_groups(ranked, effective_policy)
        selected = tuple(candidate for group in groups for candidate in group)
    else:
        selected = ranked[:effective_policy.target_items]
        groups = (selected[::2], selected[1::2])
    selected_ids = {candidate.item_id for candidate in selected}
    quota_rejected = sorted(
        candidate.item_id for candidate in ranked
        if candidate.item_id not in selected_ids
    ) if len(selected) < min(len(ranked), effective_policy.target_items) else []
    rejected = {**rejected, "source_quota": quota_rejected}
    ready = len(selected) >= effective_policy.minimum_items
    series_id = f"{topic_id}-weekly-{window.period_key}"
    parts = _make_parts(series_id, window.period_key, groups, effective_policy) if ready else ()
    minimum_shortfall = max(0, effective_policy.minimum_items - len(selected))
    target_shortfall = max(0, effective_policy.target_items - len(selected))
    policy_dict = effective_policy.as_dict()
    audit = _build_audit(
        ordered_items, candidates, selected, rejected, ranking_audit, parts,
        window, effective_policy, minimum_shortfall, target_shortfall,
    )
    return WeeklyReportPlan(
        topic_id=topic_id,
        series_id=series_id,
        period_key=window.period_key,
        window=window,
        ranked_ids=tuple(candidate.item_id for candidate in selected),
        parts=parts,
        ready=ready,
        minimum_shortfall=minimum_shortfall,
        target_shortfall=target_shortfall,
        selection_policy=policy_dict,
        selection_audit=audit,
    )


def build_weekly_report_plan(
    db: Session,
    topic_id: str,
    *,
    reference: datetime | date | None = None,
    policy: WeeklySelectionPolicy | None = None,
) -> WeeklyReportPlan:
    """Load one topic's in-week candidates and return an exact report plan."""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if topic is None:
        raise ValueError(f"Topic not found: {topic_id}")
    effective_policy = policy or _topic_policy(topic)
    window = beijing_week_window(reference)
    prefilter_rows = (
        db.query(CollectedItem.id, CollectedItem.published_at)
        .outerjoin(
            ItemTopicMembership,
            and_(
                ItemTopicMembership.item_id == CollectedItem.id,
                ItemTopicMembership.topic_id == topic_id,
            ),
        )
        .filter(or_(
            CollectedItem.topic_id == topic_id,
            ItemTopicMembership.topic_id == topic_id,
        ))
        .distinct()
        .all()
    )
    item_rows = (
        db.query(CollectedItem, ItemTopicMembership.relevance_score)
        .options(joinedload(CollectedItem.source), joinedload(CollectedItem.tags))
        .outerjoin(
            ItemTopicMembership,
            and_(
                ItemTopicMembership.item_id == CollectedItem.id,
                ItemTopicMembership.topic_id == topic_id,
            ),
        )
        .filter(
            or_(
                CollectedItem.topic_id == topic_id,
                ItemTopicMembership.topic_id == topic_id,
            ),
            CollectedItem.published_at >= window.start_utc,
            CollectedItem.published_at < window.end_utc,
        )
        .all()
    )
    items = tuple(
        _TopicItemView(
            item=item,
            relevance_score=_score(
                membership_relevance
                if membership_relevance is not None else item.relevance_score
            ),
        )
        for item, membership_relevance in item_rows
    )
    plan = select_weekly_items(
        topic_id, items, reference=reference, policy=effective_policy,
    )
    missing = sum(published_at is None for _, published_at in prefilter_rows)
    in_period = sum(
        published_at is not None
        and window.start_utc <= _as_utc(published_at) < window.end_utc
        for _, published_at in prefilter_rows
    )
    prefilter = {
        "topic_item_count": len(prefilter_rows),
        "missing_published_at": missing,
        "outside_period": len(prefilter_rows) - missing - in_period,
        "in_period": in_period,
    }
    configured_source_ids = tuple(dict.fromkeys(
        str(source_id) for source_id in (topic.source_ids or []) if source_id
    ))
    configured_sources = (
        db.query(SourceConfig)
        .filter(SourceConfig.id.in_(configured_source_ids))
        .all()
        if configured_source_ids else []
    )
    source_coverage = _source_coverage(
        configured_source_ids, configured_sources, items, effective_policy,
    )
    return replace(
        plan,
        selection_audit={
            **plan.selection_audit,
            "prefilter": prefilter,
            "source_coverage": source_coverage,
        },
    )


async def publish_weekly_digest(
    db: Session,
    topic_id: str,
    *,
    reference: datetime | date | None = None,
    policy: WeeklySelectionPolicy | None = None,
    model_id: str | None = None,
    allow_partial: bool = False,
) -> WeeklyPublicationResult:
    """Serialize publication attempts per topic/week inside this application process."""
    global _PUBLICATION_LOCKS
    period_key = beijing_week_window(reference).period_key
    key = (topic_id, period_key)
    lock = _PUBLICATION_LOCKS.get(key) or asyncio.Lock()
    _PUBLICATION_LOCKS = {**_PUBLICATION_LOCKS, key: lock}
    async with lock:
        return await _publish_weekly_digest_unlocked(
            db,
            topic_id,
            reference=reference,
            policy=policy,
            model_id=model_id,
            allow_partial=allow_partial,
        )


async def _publish_weekly_digest_unlocked(
    db: Session,
    topic_id: str,
    *,
    reference: datetime | date | None = None,
    policy: WeeklySelectionPolicy | None = None,
    model_id: str | None = None,
    allow_partial: bool = False,
) -> WeeklyPublicationResult:
    """Idempotently publish an exact two-volume weekly intelligence package."""
    topic = db.query(Topic).filter(Topic.id == topic_id).first()
    if topic is None:
        raise ValueError(f"Topic not found: {topic_id}")
    window = beijing_week_window(reference)
    existing = db.query(Report).filter(
        Report.topic_id == topic_id,
        Report.report_type == "weekly_digest",
        Report.period_key == window.period_key,
    ).all()
    frozen_plan = _frozen_plan_from_reports(topic_id, window, existing)
    plan = frozen_plan or build_weekly_report_plan(
        db, topic_id, reference=reference, policy=policy,
    )
    if not plan.ready and allow_partial and len(plan.ranked_ids) >= 60:
        configured = policy or _topic_policy(topic)
        relaxed = WeeklySelectionPolicy(
            target_items=configured.target_items,
            minimum_items=60,
            minimum_part_items=configured.minimum_part_items,
            maximum_part_items=configured.maximum_part_items,
            minimum_content_chars=configured.minimum_content_chars,
            quality_weight=configured.quality_weight,
            relevance_weight=configured.relevance_weight,
            recency_weight=configured.recency_weight,
            source_diversity_weight=configured.source_diversity_weight,
            category_diversity_weight=configured.category_diversity_weight,
            country_diversity_weight=configured.country_diversity_weight,
        )
        plan = build_weekly_report_plan(
            db, topic_id, reference=reference, policy=relaxed,
        )
    if not plan.ready:
        return WeeklyPublicationResult(
            plan=plan,
            reports=(),
            reused=False,
            warnings=(plan.selection_audit["message"],),
        )

    existing_parts = {
        report.part_index: report for report in existing if report.part_index
    }
    reports: tuple[Report, ...] = ()
    from app.report_engine import generate_report
    manifest = [
        {"part_index": part.part_index, "item_ids": list(part.item_ids)}
        for part in plan.parts
    ]

    for part in plan.parts:
        report = existing_parts.get(part.part_index)
        if report is None or report.status != "completed":
            volume = "上卷" if part.part_index == 1 else "下卷"
            title = f"{topic.name} 全球贸易风险情报周刊 {plan.period_key}（{volume}）"
            report = await generate_report(
                topic_id=topic_id,
                model_id=model_id or getattr(topic, "weekly_digest_model_id", None),
                report_type="weekly_digest",
                title_override=title,
                date_from=plan.window.start_utc.isoformat(),
                date_to=(plan.window.end_utc - timedelta(microseconds=1)).isoformat(),
                item_ids=list(part.item_ids),
                series_id=plan.series_id,
                period_key=plan.period_key,
                part_index=part.part_index,
                part_total=part.part_total,
                selection_policy=plan.selection_policy,
                selection_audit={
                    **plan.selection_audit,
                    "volume_item_ids": list(part.item_ids),
                    "manifest": manifest,
                },
            )
        elif tuple(report.item_ids or ()) != part.item_ids:
            raise ValueError("Frozen weekly manifest does not match completed report")
        reports = (*reports, report)
    return WeeklyPublicationResult(
        plan=plan,
        reports=reports,
        reused=len(existing_parts) == len(plan.parts),
        warnings=(() if plan.target_shortfall == 0 else (
            f"本周达到发布下限，但距 {len(plan.ranked_ids) + plan.target_shortfall} 条目标"
            f"还差 {plan.target_shortfall} 条。",
        )),
    )


def _frozen_plan_from_reports(
    topic_id: str,
    window: BeijingWeekWindow,
    reports: list[Report],
) -> WeeklyReportPlan | None:
    if not reports:
        return None
    first = min(reports, key=lambda report: int(report.part_index or 99))
    audit = dict(first.selection_audit or {})
    manifest = audit.get("manifest")
    if not isinstance(manifest, list):
        if len(reports) != 2:
            raise ValueError("Incomplete legacy weekly series has no frozen manifest")
        manifest = [
            {"part_index": report.part_index, "item_ids": list(report.item_ids or [])}
            for report in reports
        ]
    parts = tuple(
        WeeklyReportPart(
            str(first.series_id or f"{topic_id}-weekly-{window.period_key}"),
            window.period_key,
            int(entry.get("part_index") or 0),
            2,
            tuple(str(item_id) for item_id in entry.get("item_ids") or ()),
        )
        for entry in manifest if isinstance(entry, dict)
    )
    if len(parts) != 2 or {part.part_index for part in parts} != {1, 2}:
        raise ValueError("Frozen weekly manifest must contain exactly two volumes")
    if set(parts[0].item_ids) & set(parts[1].item_ids):
        raise ValueError("Frozen weekly manifest contains overlapping item IDs")
    ranked_ids = tuple(item_id for part in parts for item_id in part.item_ids)
    policy = dict(first.selection_policy or audit.get("policy") or {})
    target = int(policy.get("target_items") or len(ranked_ids))
    minimum = int(policy.get("minimum_items") or min(60, len(ranked_ids)))
    return WeeklyReportPlan(
        topic_id=topic_id,
        series_id=parts[0].series_id,
        period_key=window.period_key,
        window=window,
        ranked_ids=ranked_ids,
        parts=tuple(sorted(parts, key=lambda part: part.part_index)),
        ready=len(ranked_ids) >= minimum,
        minimum_shortfall=max(0, minimum - len(ranked_ids)),
        target_shortfall=max(0, target - len(ranked_ids)),
        selection_policy=policy,
        selection_audit={**audit, "frozen_manifest_reused": True},
    )


def _beijing_reference(reference: datetime | date | None) -> datetime:
    if reference is None:
        return datetime.now(UTC).astimezone(BEIJING)
    if isinstance(reference, datetime):
        if reference.tzinfo is None:
            return reference.replace(tzinfo=BEIJING)
        return reference.astimezone(BEIJING)
    return datetime.combine(reference, time.min, tzinfo=BEIJING)


def _topic_policy(topic: Topic) -> WeeklySelectionPolicy:
    target = int(getattr(topic, "weekly_digest_target_items", None) or 80)
    minimum = int(getattr(topic, "weekly_digest_min_items", None) or 60)
    maximum_part = int(getattr(topic, "weekly_digest_part_size", None) or 40)
    return WeeklySelectionPolicy(
        target_items=target,
        minimum_items=minimum,
        maximum_part_items=maximum_part,
    )


def _source_coverage(
    configured_source_ids: tuple[str, ...],
    configured_sources: Iterable[SourceConfig],
    in_period_items: Iterable[CollectedItem],
    policy: WeeklySelectionPolicy,
) -> dict[str, Any]:
    """Summarize whether the configured source portfolio can support a digest."""
    sources = tuple(configured_sources)
    items = tuple(in_period_items)
    publication_ready = tuple(
        source for source in sources
        if evaluate_collection_policy(source).content_depth == "full"
    )
    publishers = {
        publisher for item in items
        if (publisher := _publisher_identity(item))
    }
    return {
        "configured_source_count": len(configured_source_ids),
        "publication_ready_source_count": len(publication_ready),
        "in_period_source_count": len({str(item.source_id) for item in items}),
        "in_period_publisher_count": len(publishers),
        "publisher_shortfall": max(
            0, policy.minimum_sources_per_part - len(publishers),
        ),
        "countries": sorted({
            value for source in publication_ready
            for value in _coverage_values(
                source.country_focus, _COUNTRY_COVERAGE_ALIASES, uppercase=True,
            )
        }),
        "languages": sorted({
            value for source in publication_ready
            for value in _coverage_values(
                source.languages, _LANGUAGE_COVERAGE_ALIASES, uppercase=False,
            )
        }),
    }


def _coverage_values(
    value: Any,
    aliases: dict[str, str],
    *,
    uppercase: bool,
) -> tuple[str, ...]:
    normalized: tuple[str, ...] = ()
    for raw_value in _as_values(value):
        casefolded = raw_value.casefold()
        if casefolded in aliases:
            candidate = aliases[casefolded]
        elif raw_value.isascii() and raw_value.isalpha() and len(raw_value) <= 3:
            candidate = raw_value.upper() if uppercase else raw_value.lower()
        else:
            candidate = raw_value
        normalized = (*normalized, candidate)
    return tuple(dict.fromkeys(normalized))


def _filter_candidates(
    items: tuple[Any, ...],
    window: BeijingWeekWindow,
    policy: WeeklySelectionPolicy,
) -> tuple[tuple[_Candidate, ...], dict[str, list[str]]]:
    candidates_by_identity: dict[str, _Candidate] = {}
    rejected = {
        "missing_published_at": [],
        "outside_period": [],
        "short_content": [],
        "discarded": [],
        "non_chinese": [],
        "low_quality": [],
        "low_relevance": [],
        "low_publishability": [],
        "source_policy": [],
        "duplicate": [],
        "source_quota": [],
    }
    for item in items:
        item_id = str(_get(item, "id") or "")
        published_at = _as_utc(_get(item, "published_at"))
        reason = _rejection_reason(item, published_at, window, policy)
        if reason:
            rejected = {**rejected, reason: [*rejected[reason], item_id]}
            continue
        assert published_at is not None
        candidate = _candidate(item, item_id, published_at, window, policy)
        identity = _candidate_identity(item, item_id)
        previous = candidates_by_identity.get(identity)
        if previous is None:
            candidates_by_identity = {**candidates_by_identity, identity: candidate}
            continue
        winner, duplicate = _prefer_candidate(previous, candidate)
        candidates_by_identity = {**candidates_by_identity, identity: winner}
        rejected = {
            **rejected,
            "duplicate": sorted([*rejected["duplicate"], duplicate.item_id]),
        }
    return tuple(candidates_by_identity.values()), rejected


def _candidate_identity(item: Any, item_id: str) -> str:
    """Prefer canonical source URLs; use hashes only for URL-less records."""
    url = _canonical_url(_get(item, "url"))
    if url:
        return f"url:{url}"
    content_hash = str(_get(item, "content_hash") or "").strip().casefold()
    return f"hash:{content_hash}" if content_hash else f"item:{item_id}"


def _canonical_url(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        parsed = urlsplit(text)
    except ValueError:
        return text.casefold()
    query = urlencode([
        (key, item_value)
        for key, item_value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.casefold().startswith("utm_")
        and key.casefold() not in {"fbclid", "gclid"}
    ])
    path = parsed.path.rstrip("/") or "/"
    return urlunsplit((
        parsed.scheme.casefold(), parsed.netloc.casefold(), path, query, "",
    ))


def _publisher_identity(item: Any) -> str:
    """Use the original publisher domain so duplicate configs share one quota."""
    metadata = _get(item, "raw_metadata")
    if isinstance(metadata, dict):
        explicit = str(metadata.get("publisher_id") or "").strip().casefold()
        if explicit:
            return f"publisher:{explicit}"
    try:
        host = (urlsplit(str(_get(item, "url") or "")).hostname or "").casefold()
    except ValueError:
        host = ""
    normalized_host = host[4:] if host.startswith("www.") else host
    if normalized_host:
        return f"domain:{normalized_host}"
    source_id = str(_get(item, "source_id") or "").casefold()
    return f"source:{source_id}"


def _prefer_candidate(
    left: _Candidate, right: _Candidate,
) -> tuple[_Candidate, _Candidate]:
    def sort_key(candidate: _Candidate) -> tuple[float, float, float, str]:
        return (
            candidate.base_score,
            candidate.quality,
            candidate.published_at.timestamp(),
            candidate.item_id,
        )

    return (right, left) if sort_key(right) > sort_key(left) else (left, right)


def _rejection_reason(
    item: Any,
    published_at: datetime | None,
    window: BeijingWeekWindow,
    policy: WeeklySelectionPolicy,
) -> str | None:
    if published_at is None:
        return "missing_published_at"
    if not window.start_utc <= published_at < window.end_utc:
        return "outside_period"
    if len(_body_text(item)) < policy.minimum_content_chars:
        return "short_content"
    status = str(_get(item, "status") or "").casefold()
    if status.endswith("discarded"):
        return "discarded"
    if str(_get(item, "language") or "").casefold() not in {"zh", "zh-cn", "cn"}:
        return "non_chinese"
    if not is_substantially_chinese(
        _body_text(item), minimum_han=20,
    ):
        return "non_chinese"
    if _score(_get(item, "quality_score")) < policy.minimum_quality:
        return "low_quality"
    if _score(_get(item, "relevance_score")) < policy.minimum_relevance:
        return "low_relevance"
    if _publishability(item) < policy.minimum_publishability:
        return "low_publishability"
    source = _get(item, "source")
    if source is not None and not evaluate_collection_policy(source).llm_ingest_allowed:
        return "source_policy"
    return None


def _candidate(
    item: Any,
    item_id: str,
    published_at: datetime,
    window: BeijingWeekWindow,
    policy: WeeklySelectionPolicy,
) -> _Candidate:
    quality = _score(_get(item, "quality_score"))
    relevance = _score(_get(item, "relevance_score"))
    elapsed = (published_at - window.start_utc).total_seconds()
    duration = (window.end_utc - window.start_utc).total_seconds()
    recency = max(0.0, min(1.0, elapsed / duration))
    base_score = (
        quality * policy.quality_weight
        + relevance * policy.relevance_weight
        + recency * policy.recency_weight
    )
    return _Candidate(
        item_id=item_id,
        published_at=published_at,
        source=_publisher_identity(item),
        category=str(_get(item, "category") or ""),
        countries=_countries(item),
        quality=quality,
        relevance=relevance,
        recency=recency,
        base_score=base_score,
    )


def _rank_candidates(
    candidates: tuple[_Candidate, ...],
    policy: WeeklySelectionPolicy,
) -> tuple[tuple[_Candidate, ...], tuple[dict[str, Any], ...]]:
    remaining = candidates
    ranked: tuple[_Candidate, ...] = ()
    audit: tuple[dict[str, Any], ...] = ()
    source_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}
    country_counts: dict[str, int] = {}
    while remaining:
        scored = tuple(
            (candidate, _diversity_bonus(
                candidate, source_counts, category_counts, country_counts, policy,
            ))
            for candidate in remaining
        )
        chosen, bonus = min(
            scored,
            key=lambda pair: (
                -(pair[0].base_score + pair[1]),
                -pair[0].base_score,
                -pair[0].published_at.timestamp(),
                pair[0].item_id,
            ),
        )
        ranked = (*ranked, chosen)
        audit = (*audit, _ranking_record(len(ranked), chosen, bonus))
        remaining = tuple(candidate for candidate in remaining if candidate is not chosen)
        source_counts = _increment(source_counts, chosen.source)
        category_counts = _increment(category_counts, chosen.category)
        for country in chosen.countries:
            country_counts = _increment(country_counts, country)
    return ranked, audit


def _diversity_bonus(
    candidate: _Candidate,
    source_counts: dict[str, int],
    category_counts: dict[str, int],
    country_counts: dict[str, int],
    policy: WeeklySelectionPolicy,
) -> float:
    source = _dimension_bonus(candidate.source, source_counts, policy.source_diversity_weight)
    category = _dimension_bonus(
        candidate.category, category_counts, policy.category_diversity_weight,
    )
    country = 0.0
    if candidate.countries:
        least_seen = min(country_counts.get(value, 0) for value in candidate.countries)
        country = policy.country_diversity_weight / (1 + least_seen)
    return source + category + country


def _dimension_bonus(value: str, counts: dict[str, int], weight: float) -> float:
    return weight / (1 + counts.get(value, 0)) if value else 0.0


def _increment(counts: dict[str, int], value: str) -> dict[str, int]:
    return {**counts, value: counts.get(value, 0) + 1} if value else counts


def _ranking_record(rank: int, candidate: _Candidate, bonus: float) -> dict[str, Any]:
    return {
        "rank": rank,
        "item_id": candidate.item_id,
        "quality": round(candidate.quality, 6),
        "relevance": round(candidate.relevance, 6),
        "recency": round(candidate.recency, 6),
        "base_score": round(candidate.base_score, 6),
        "diversity_bonus": round(bonus, 6),
        "total_score": round(candidate.base_score + bonus, 6),
        "source": candidate.source or None,
        "category": candidate.category or None,
        "countries": list(candidate.countries),
    }


def _allocate_volume_groups(
    ranked: tuple[_Candidate, ...],
    policy: WeeklySelectionPolicy,
) -> tuple[tuple[_Candidate, ...], tuple[_Candidate, ...]]:
    maximum = min(len(ranked), policy.target_items)
    for total in range(maximum, 1, -1):
        sizes = ((total + 1) // 2, total // 2)
        caps = tuple(
            max(1, int(size * policy.maximum_source_share)) for size in sizes
        )
        selected: tuple[_Candidate, ...] = ()
        total_source_counts: dict[str, int] = {}
        for candidate in ranked:
            if total_source_counts.get(candidate.source, 0) >= caps[0] + caps[1]:
                continue
            selected = (*selected, candidate)
            total_source_counts = _increment(total_source_counts, candidate.source)
            if len(selected) == total:
                break
        if len(selected) != total:
            continue
        groups = _split_selected_by_source_caps(selected, sizes, caps)
        if groups is None:
            continue
        source_counts = tuple(
            {source: sum(candidate.source == source for candidate in group)
             for source in {candidate.source for candidate in group}}
            for group in groups
        )
        if total >= policy.minimum_items and any(
            len(source_counts[index]) < policy.minimum_sources_per_part
            for index in (0, 1)
        ):
            continue
        return groups
    return ((), ())


def _split_selected_by_source_caps(
    selected: tuple[_Candidate, ...],
    sizes: tuple[int, int],
    caps: tuple[int, int],
) -> tuple[tuple[_Candidate, ...], tuple[_Candidate, ...]] | None:
    by_source: dict[str, tuple[_Candidate, ...]] = {}
    for candidate in selected:
        by_source = {
            **by_source,
            candidate.source: (*by_source.get(candidate.source, ()), candidate),
        }
    allocation_zero = {
        source: max(0, len(candidates) - caps[1])
        for source, candidates in by_source.items()
    }
    remaining = sizes[0] - sum(allocation_zero.values())
    for source, candidates in by_source.items():
        available = min(len(candidates), caps[0]) - allocation_zero[source]
        addition = min(max(0, available), max(0, remaining))
        allocation_zero = {
            **allocation_zero, source: allocation_zero[source] + addition,
        }
        remaining -= addition
    if remaining != 0:
        return None
    group_zero_ids = {
        candidate.item_id
        for source, candidates in by_source.items()
        for candidate in candidates[:allocation_zero[source]]
    }
    groups = (
        tuple(candidate for candidate in selected if candidate.item_id in group_zero_ids),
        tuple(candidate for candidate in selected if candidate.item_id not in group_zero_ids),
    )
    if tuple(len(group) for group in groups) != sizes:
        return None
    return groups


def _make_parts(
    series_id: str,
    period_key: str,
    groups: tuple[tuple[_Candidate, ...], tuple[_Candidate, ...]],
    policy: WeeklySelectionPolicy,
) -> tuple[WeeklyReportPart, ...]:
    if any(
        not policy.minimum_part_items <= len(group) <= policy.maximum_part_items
        for group in groups
    ):
        return ()
    return tuple(
        WeeklyReportPart(
            series_id, period_key, index, 2,
            tuple(candidate.item_id for candidate in group),
        )
        for index, group in enumerate(groups, 1)
    )


def _build_audit(
    input_items: tuple[Any, ...],
    candidates: tuple[_Candidate, ...],
    selected: tuple[_Candidate, ...],
    rejected: dict[str, list[str]],
    ranking: tuple[dict[str, Any], ...],
    parts: tuple[WeeklyReportPart, ...],
    window: BeijingWeekWindow,
    policy: WeeklySelectionPolicy,
    minimum_shortfall: int,
    target_shortfall: int,
) -> dict[str, Any]:
    status = "ready" if not minimum_shortfall else "insufficient_candidates"
    message = (
        f"至少还需 {minimum_shortfall} 条合格信息才能生成两卷周报"
        if minimum_shortfall
        else (
            f"已满足发布下限，距 {policy.target_items} 条目标还差 "
            f"{target_shortfall} 条"
            if target_shortfall
            else "已达到周报目标"
        )
    )
    selected_ids = {candidate.item_id for candidate in selected}
    not_selected = sorted(
        candidate.item_id for candidate in candidates if candidate.item_id not in selected_ids
    )
    return {
        "status": status,
        "message": message,
        "window": window.as_dict(),
        "policy": policy.as_dict(),
        "input_count": len(input_items),
        "eligible_count": len(candidates),
        "selected_count": len(selected),
        "minimum_shortfall": minimum_shortfall,
        "target_shortfall": target_shortfall,
        "part_sizes": [len(part.item_ids) for part in parts],
        "rejected": {key: [*values] for key, values in rejected.items()},
        "not_selected": not_selected,
        "ranking": [dict(record) for record in ranking],
    }


def _body_text(item: Any) -> str:
    metadata = _get(item, "raw_metadata")
    translation = metadata.get("translation_zh") if isinstance(metadata, dict) else None
    translated = translation.get("content_zh") if isinstance(translation, dict) else None
    value = translated or _get(item, "content") or ""
    return " ".join(str(value).split())


def _publishability(item: Any) -> int:
    metadata = _get(item, "raw_metadata")
    profile = metadata.get("intelligence_profile") if isinstance(metadata, dict) else None
    value = profile.get("publishability") if isinstance(profile, dict) else None
    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return 0


def _countries(item: Any) -> tuple[str, ...]:
    values: tuple[str, ...] = ()
    entities = _get(item, "entities")
    metadata = _get(item, "raw_metadata")
    source = _get(item, "source")
    if isinstance(entities, dict):
        values = (*values, *_as_values(entities.get("countries") or entities.get("country")))
    if isinstance(metadata, dict):
        values = (*values, *_as_values(metadata.get("countries") or metadata.get("country")))
    values = (*values, *_as_values(_get(source, "country_focus")))
    for tag in _get(item, "tags") or ():
        if str(_get(tag, "namespace") or "").lower() == "country":
            values = (*values, *_as_values(_get(tag, "value")))
    return tuple(sorted(set(value for value in values if value)))


def _as_values(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value.strip(),) if value.strip() else ()
    if isinstance(value, (list, tuple, set)):
        return tuple(str(item).strip() for item in value if str(item).strip())
    return (str(value).strip(),) if str(value).strip() else ()


def _as_utc(value: Any) -> datetime | None:
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except (TypeError, ValueError):
            return None
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _score(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value or 0.0)))
    except (TypeError, ValueError):
        return 0.0


def _get(value: Any, key: str) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
