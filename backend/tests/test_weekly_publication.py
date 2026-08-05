"""End-to-end weekly publication contracts."""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import CollectedItem, Report, SourceChannel, SourceConfig, Topic
from app.weekly_report_engine import publish_weekly_digest


def test_weekly_publication_creates_two_exact_idempotent_forty_item_documents(
    tmp_path, monkeypatch,
) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'weekly.db'}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine)
    db = factory()
    reference = datetime(2026, 7, 29, 12, tzinfo=timezone.utc)
    db.add(Topic(
        id="topic-weekly",
        name="全球贸易监管",
        weekly_digest_enabled=True,
        weekly_digest_target_items=80,
        weekly_digest_part_size=40,
        weekly_digest_min_items=60,
    ))
    db.add_all([
        SourceConfig(
            id=f"source-{source_index}", name=f"Verified source {source_index}",
            channel=SourceChannel.WEB_SCRAPE, is_active=True, is_configured=True,
            verification_status="verified", robots_status="allowed",
            terms_status="public_domain", llm_ingest_allowed=True,
        )
        for source_index in range(8)
    ])
    db.add_all([
        CollectedItem(
            id=f"item-{index:03d}",
            source_id=f"source-{index % 8}",
            topic_id="topic-weekly",
            title=f"中文情报 {index}",
            content="完整的中文全球贸易风险情报正文。" * 20,
            content_hash=f"hash-{index:03d}",
                url=f"https://publisher-{index % 8}.example/intelligence/{index}",
            language="zh",
            status="enriched",
            category=f"分类-{index % 8}",
            entities={"countries": [f"国家-{index % 12}"]},
            quality_score=0.9,
            relevance_score=0.9,
            published_at=reference + timedelta(minutes=index),
            raw_metadata={"intelligence_profile": {"publishability": 90}},
        )
        for index in range(80)
    ])
    db.commit()
    monkeypatch.setattr("app.report_engine.SessionLocal", factory)
    monkeypatch.setattr(
        "app.report_engine._export_report_files", lambda *_args, **_kwargs: None,
    )

    first = asyncio.run(publish_weekly_digest(
        db, "topic-weekly", reference=reference,
    ))
    frozen_ids = tuple(item_id for report in first.reports for item_id in report.item_ids)
    db.add_all([
        CollectedItem(
            id=f"late-{index:03d}", source_id=f"source-{index % 8}",
            topic_id="topic-weekly", title=f"晚到高分情报 {index}",
            content="晚到但不应改变已冻结周刊的中文情报正文。" * 20,
            content_hash=f"late-hash-{index:03d}",
            url=f"https://late.example/intelligence/{index}", language="zh",
            status="enriched", category="晚到信息",
            entities={"countries": [f"国家-{index % 8}"]},
            quality_score=0.99, relevance_score=0.99,
            published_at=reference + timedelta(hours=2, minutes=index),
            raw_metadata={"intelligence_profile": {"publishability": 99}},
        )
        for index in range(8)
    ])
    failed_part = db.query(Report).filter(
        Report.topic_id == "topic-weekly", Report.part_index == 2,
    ).one()
    failed_part.status = "generating"
    failed_part.generation_owner = "other-process"
    failed_part.generation_lease_until = datetime.now(timezone.utc) + timedelta(minutes=10)
    db.commit()

    with pytest.raises(RuntimeError, match="another process"):
        asyncio.run(publish_weekly_digest(
            db, "topic-weekly", reference=reference,
        ))

    db.refresh(failed_part)
    assert failed_part.generation_owner == "other-process"
    failed_part.generation_lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()
    monkeypatch.setattr(
        "app.report_engine._export_report_files",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("disk full")),
    )
    with pytest.raises(RuntimeError, match="disk full"):
        asyncio.run(publish_weekly_digest(
            db, "topic-weekly", reference=reference,
        ))
    db.refresh(failed_part)
    assert failed_part.status == "failed"
    assert failed_part.generation_owner is None
    assert failed_part.generation_lease_until is None

    monkeypatch.setattr(
        "app.report_engine._export_report_files", lambda *_args, **_kwargs: None,
    )
    second = asyncio.run(publish_weekly_digest(
        db, "topic-weekly", reference=reference,
    ))

    assert first.plan.ready is True
    assert [report.item_count for report in first.reports] == [40, 40]
    assert set(first.reports[0].item_ids).isdisjoint(first.reports[1].item_ids)
    assert all(report.report_type == "weekly_digest" for report in first.reports)
    assert all(report.status == "completed" for report in first.reports)
    assert all("全球贸易风险情报周刊" in report.title for report in first.reports)
    assert all("### 中文情报" in report.content for report in first.reports)
    assert second.reused is True
    assert [report.id for report in second.reports] == [
        report.id for report in first.reports
    ]
    assert tuple(second.plan.ranked_ids) == frozen_ids
    assert all(not item_id.startswith("late-") for item_id in second.plan.ranked_ids)
    assert second.reports[1].status == "completed"
    assert second.reports[1].retry_count == 2
    db.close()
