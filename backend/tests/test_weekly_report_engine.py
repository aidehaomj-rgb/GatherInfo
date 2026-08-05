"""Weekly report selection contracts."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import (
    CollectedItem, ItemTopicMembership, SourceChannel, SourceConfig, Topic,
)
from app.weekly_report_engine import (
    WeeklySelectionPolicy,
    beijing_week_window,
    build_weekly_report_plan,
    select_weekly_items,
)


UTC = timezone.utc


def _item(
    item_id: str,
    published_at: datetime | None,
    *,
    source: str = "source-a",
    category: str = "policy",
    country: str = "CN",
    quality: float = 0.8,
    relevance: float = 0.8,
    content_length: int = 220,
    url: str | None = None,
    content_hash: str | None = None,
    language: str = "zh",
    publishability: int = 85,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=item_id,
        published_at=published_at,
        source_id=source,
        category=category,
        quality_score=quality,
        relevance_score=relevance,
        content="正" * content_length,
        content_hash=content_hash,
        url=url,
        summary="",
        entities={"countries": [country]},
        tags=[],
        source=None,
        language=language,
        status="enriched",
        raw_metadata={"intelligence_profile": {"publishability": publishability}},
    )


def _weekly_items(count: int, published_at: datetime) -> list[SimpleNamespace]:
    return [
        _item(
            f"item-{index:03d}",
            published_at + timedelta(minutes=index),
            source=f"source-{index % 8}",
            category=f"category-{index % 6}",
            country=f"country-{index % 10}",
            quality=0.7 + (index % 5) * 0.03,
            relevance=0.72 + (index % 7) * 0.02,
        )
        for index in range(count)
    ]


def test_beijing_natural_week_uses_inclusive_start_and_exclusive_end() -> None:
    reference = datetime(2026, 8, 2, 23, 59, tzinfo=timezone(timedelta(hours=8)))

    window = beijing_week_window(reference)

    assert window.period_key == "2026-W31"
    assert window.start_utc == datetime(2026, 7, 26, 16, tzinfo=UTC)
    assert window.end_utc == datetime(2026, 8, 2, 16, tzinfo=UTC)
    candidates = [
        _item("at-start", window.start_utc),
        _item("before-end", window.end_utc - timedelta(microseconds=1)),
        _item("at-end", window.end_utc),
    ]

    plan = select_weekly_items("topic-a", candidates, reference=reference)

    assert set(plan.ranked_ids) == {"at-start", "before-end"}
    assert plan.selection_audit["rejected"]["outside_period"] == ["at-end"]


def test_selection_filters_missing_dates_and_short_body_with_audit() -> None:
    reference = datetime(2026, 7, 29, 12, tzinfo=UTC)
    candidates = [
        _item("eligible", reference),
        _item("missing-date", None),
        _item("short-body", reference, content_length=179),
    ]

    plan = select_weekly_items("topic-a", candidates, reference=reference)

    assert plan.ranked_ids == ("eligible",)
    assert plan.ready is False
    assert plan.minimum_shortfall == 59
    assert plan.selection_audit["rejected"]["missing_published_at"] == ["missing-date"]
    assert plan.selection_audit["rejected"]["short_content"] == ["short-body"]


def test_duplicate_selection_prefers_better_item_across_sources() -> None:
    published_at = datetime(2026, 7, 29, 12, tzinfo=UTC)
    candidates = [
        _item(
            "url-low", published_at, source="source-a", quality=0.7,
            relevance=0.7, url="https://EXAMPLE.com/news/rule/?utm_source=a#top",
        ),
        _item(
            "url-best", published_at, source="source-b", quality=0.92,
            relevance=0.9, url="https://example.com/news/rule",
        ),
        _item(
            "hash-low", published_at, source="source-a", quality=0.65,
            relevance=0.8, content_hash="ABC123",
        ),
        _item(
            "hash-best", published_at, source="source-c", quality=0.88,
            relevance=0.86, content_hash="abc123",
        ),
    ]

    plan = select_weekly_items("topic-a", candidates, reference=published_at)

    assert set(plan.ranked_ids) == {"url-best", "hash-best"}
    assert plan.selection_audit["rejected"]["duplicate"] == ["url-low"]
    assert plan.selection_audit["rejected"]["low_quality"] == ["hash-low"]


def test_url_identity_takes_priority_over_matching_content_hash() -> None:
    published_at = datetime(2026, 7, 29, 12, tzinfo=UTC)
    candidates = [
        _item(
            "publisher-a", published_at, url="https://a.example/story",
            content_hash="same-content",
        ),
        _item(
            "publisher-b", published_at, url="https://b.example/story",
            content_hash="same-content",
        ),
    ]

    plan = select_weekly_items("topic-a", candidates, reference=published_at)

    assert set(plan.ranked_ids) == {"publisher-a", "publisher-b"}
    assert plan.selection_audit["rejected"]["duplicate"] == []


def test_ranking_is_deterministic_and_rewards_dimension_diversity() -> None:
    published_at = datetime(2026, 7, 29, 12, tzinfo=UTC)
    highest = _item(
        "highest", published_at, source="alpha", category="policy", country="CN",
        quality=0.9, relevance=0.9,
    )
    near_duplicate = _item(
        "near-duplicate", published_at, source="alpha", category="policy", country="CN",
        quality=0.89, relevance=0.89,
    )
    diverse = _item(
        "diverse", published_at, source="beta", category="enforcement", country="US",
        quality=0.88, relevance=0.88,
    )

    first = select_weekly_items(
        "topic-a", [near_duplicate, diverse, highest], reference=published_at,
    )
    second = select_weekly_items(
        "topic-a", [highest, diverse, near_duplicate], reference=published_at,
    )

    assert first.ranked_ids == second.ranked_ids
    assert first.ranked_ids[:3] == ("highest", "diverse", "near-duplicate")
    assert first.selection_audit["ranking"][1]["diversity_bonus"] > (
        first.selection_audit["ranking"][2]["diversity_bonus"]
    )


def test_exact_target_splits_into_two_forty_item_volumes() -> None:
    published_at = datetime(2026, 7, 29, 12, tzinfo=UTC)

    plan = select_weekly_items(
        "topic-a", _weekly_items(80, published_at), reference=published_at,
    )

    assert plan.ready is True
    assert [len(part.item_ids) for part in plan.parts] == [40, 40]
    assert [part.part_index for part in plan.parts] == [1, 2]
    assert all(part.part_total == 2 for part in plan.parts)
    assert plan.target_shortfall == 0
    assert plan.series_id == "topic-a-weekly-2026-W31"
    fields = plan.parts[0].report_fields(
        plan.selection_policy, plan.selection_audit,
    )
    assert fields["series_id"] == plan.series_id
    assert fields["period_key"] == "2026-W31"
    assert fields["part_index"] == 1
    assert fields["part_total"] == 2
    assert fields["item_count"] == 40


def test_sixty_five_candidates_split_evenly_and_report_target_gap() -> None:
    published_at = datetime(2026, 7, 29, 12, tzinfo=UTC)

    plan = select_weekly_items(
        "topic-a", _weekly_items(65, published_at), reference=published_at,
    )

    assert plan.ready is True
    assert [len(part.item_ids) for part in plan.parts] == [33, 32]
    assert plan.minimum_shortfall == 0
    assert plan.target_shortfall == 15
    assert plan.selection_audit["part_sizes"] == [33, 32]


def test_fewer_than_sixty_candidates_returns_explicit_publication_gap() -> None:
    published_at = datetime(2026, 7, 29, 12, tzinfo=UTC)

    plan = select_weekly_items(
        "topic-a", _weekly_items(55, published_at), reference=published_at,
    )

    assert plan.ready is False
    assert plan.parts == ()
    assert plan.minimum_shortfall == 5
    assert plan.target_shortfall == 25
    assert plan.selection_audit["status"] == "insufficient_candidates"
    assert plan.selection_audit["message"] == (
        "至少还需 5 条合格信息才能生成两卷周报"
    )


def test_single_source_cannot_fill_a_publishable_weekly_package() -> None:
    published_at = datetime(2026, 7, 29, 12, tzinfo=UTC)
    items = [
        _item(f"single-{index}", published_at + timedelta(minutes=index), source="only")
        for index in range(80)
    ]

    plan = select_weekly_items("topic-a", items, reference=published_at)

    assert plan.ready is False
    assert plan.minimum_shortfall > 0
    assert plan.selection_audit["rejected"]["source_quota"]


def test_multiple_config_ids_for_same_publishers_do_not_bypass_source_quota() -> None:
    published_at = datetime(2026, 7, 29, 12, tzinfo=UTC)
    items = [
        _item(
            f"duplicate-config-{index}",
            published_at + timedelta(minutes=index),
            source=f"config-{index % 8}",
            url=f"https://publisher-{index % 4}.example/news/{index}",
        )
        for index in range(80)
    ]

    plan = select_weekly_items("topic-a", items, reference=published_at)

    assert plan.ready is False
    assert plan.selection_audit["rejected"]["source_quota"]


def test_quality_language_and_publishability_are_hard_gates() -> None:
    published_at = datetime(2026, 7, 29, 12, tzinfo=UTC)
    low_quality = _item("low-quality", published_at, quality=0.4)
    non_chinese = _item("non-chinese", published_at, language="en")
    low_publishability = _item(
        "low-publishability", published_at, publishability=30,
    )

    plan = select_weekly_items(
        "topic-a", [low_quality, non_chinese, low_publishability],
        reference=published_at,
    )

    rejected = plan.selection_audit["rejected"]
    assert rejected["low_quality"] == ["low-quality"]
    assert rejected["non_chinese"] == ["non-chinese"]
    assert rejected["low_publishability"] == ["low-publishability"]


def test_database_orchestration_queries_only_the_requested_topic_and_week() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    reference = datetime(2026, 7, 29, 12, tzinfo=UTC)
    try:
        db.add_all([
            Topic(id="topic-a", name="目标主题"),
            Topic(id="topic-b", name="其他主题"),
            *[
                SourceConfig(
                    id=f"source-{source_index}", name=f"测试来源 {source_index}",
                    channel=SourceChannel.WEB_SCRAPE, country_focus=["CN"],
                    is_active=True, is_configured=True, verification_status="verified",
                    robots_status="allowed", terms_status="public_domain",
                    llm_ingest_allowed=True,
                )
                for source_index in range(8)
            ],
        ])
        for index in range(65):
            db.add(CollectedItem(
                id=f"db-{index:03d}", source_id=f"source-{index % 8}", topic_id="topic-a",
                title=f"周报条目 {index}", content="完整正文" * 60,
                category=f"category-{index % 4}", quality_score=0.8,
                relevance_score=0.8, published_at=reference + timedelta(minutes=index),
                language="zh", status="enriched",
                raw_metadata={"intelligence_profile": {"publishability": 85}},
            ))
        db.add(CollectedItem(
            id="other-topic", source_id="source-0", topic_id="topic-b",
            title="其他主题", content="完整正文" * 60,
            published_at=reference, language="zh", status="enriched",
            quality_score=0.8, relevance_score=0.8,
            raw_metadata={"intelligence_profile": {"publishability": 85}},
        ))
        db.add(CollectedItem(
            id="previous-week", source_id="source-0", topic_id="topic-a",
            title="上周信息", content="完整正文" * 60,
            published_at=datetime(2026, 7, 20, 12, tzinfo=UTC),
            language="zh", status="enriched", quality_score=0.8,
            relevance_score=0.8,
            raw_metadata={"intelligence_profile": {"publishability": 85}},
        ))
        db.commit()

        plan = build_weekly_report_plan(db, "topic-a", reference=reference)

        assert plan.ready is True
        assert len(plan.ranked_ids) == 65
        assert [len(part.item_ids) for part in plan.parts] == [33, 32]
        assert "other-topic" not in plan.ranked_ids
        assert "previous-week" not in plan.ranked_ids
        assert plan.selection_policy == WeeklySelectionPolicy().as_dict()
        assert plan.selection_audit["prefilter"] == {
            "topic_item_count": 66,
            "missing_published_at": 0,
            "outside_period": 1,
            "in_period": 65,
        }
    finally:
        db.close()
        engine.dispose()


def test_weekly_report_plan_reports_prefilter_counts_with_no_in_window_items() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    reference = datetime(2026, 8, 4, 12, tzinfo=UTC)
    try:
        db.add_all([
            Topic(
                id="topic-empty-week", name="空周主题",
                source_ids=["source-empty-week"],
            ),
            SourceConfig(
                id="source-empty-week", name="测试来源",
                channel=SourceChannel.WEB_SCRAPE, is_active=True, is_configured=True,
                verification_status="verified", robots_status="allowed",
                terms_status="public_domain", llm_ingest_allowed=True,
                country_focus=["US", "美国"], languages=["en", "英文"],
            ),
            CollectedItem(
                id="missing-date", source_id="source-empty-week",
                topic_id="topic-empty-week", title="无日期", content="完整正文" * 60,
                published_at=None, language="zh", status="enriched",
            ),
            CollectedItem(
                id="old-date", source_id="source-empty-week",
                topic_id="topic-empty-week", title="旧信息", content="完整正文" * 60,
                published_at=datetime(2026, 7, 20, 12, tzinfo=UTC),
                language="zh", status="enriched",
            ),
        ])
        db.commit()

        plan = build_weekly_report_plan(db, "topic-empty-week", reference=reference)

        assert plan.ready is False
        assert plan.selection_audit["input_count"] == 0
        assert plan.selection_audit["prefilter"] == {
            "topic_item_count": 2,
            "missing_published_at": 1,
            "outside_period": 1,
            "in_period": 0,
        }
        assert plan.selection_audit["source_coverage"] == {
            "configured_source_count": 1,
            "publication_ready_source_count": 1,
            "in_period_source_count": 0,
            "in_period_publisher_count": 0,
            "publisher_shortfall": 5,
            "countries": ["US"],
            "languages": ["en"],
        }
    finally:
        db.close()
        engine.dispose()


def test_weekly_plan_uses_topic_membership_relevance_instead_of_global_score() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    reference = datetime(2026, 8, 4, 12, tzinfo=UTC)
    try:
        db.add_all([
            Topic(id="topic-a", name="主题 A", source_ids=["source-shared"]),
            Topic(id="topic-b", name="主题 B", source_ids=["source-shared"]),
            SourceConfig(
                id="source-shared", name="共享正式来源",
                channel=SourceChannel.WEB_SCRAPE, is_active=True, is_configured=True,
                verification_status="verified", robots_status="allowed",
                terms_status="public_domain", llm_ingest_allowed=True,
            ),
            CollectedItem(
                id="shared-item", source_id="source-shared", topic_id="topic-a",
                title="跨主题共享信息", content="完整中文正文" * 60,
                published_at=datetime(2026, 8, 3, 8, tzinfo=UTC),
                language="zh", status="enriched", quality_score=0.9,
                relevance_score=0.95,
                raw_metadata={"intelligence_profile": {"publishability": 90}},
            ),
        ])
        db.commit()
        db.add(ItemTopicMembership(
            item_id="shared-item", topic_id="topic-b", relevance_score=0.70,
        ))
        db.commit()

        plan = build_weekly_report_plan(
            db, "topic-b", reference=reference,
            policy=WeeklySelectionPolicy(minimum_relevance=0.80),
        )

        assert plan.ranked_ids == ()
        assert plan.selection_audit["rejected"]["low_relevance"] == ["shared-item"]
    finally:
        db.close()
        engine.dispose()
