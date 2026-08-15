"""Tests for stable, customs-focused featured intelligence selection."""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import CollectedItem, SourceChannel, SourceConfig, SystemConfig
from app.services.featured_intelligence import (
    choose_featured_ids, get_featured_items, score_featured_item,
)


def _item(title: str, content: str, review: dict | None = None):
    return SimpleNamespace(
        id=title,
        title=title,
        summary="完整摘要，说明监管主体、措施、对象及影响。" * 3,
        content=content,
        raw_metadata={"quality_review": review or {}},
        quality_score=0.8,
        relevance_score=0.8,
        collected_at=datetime.now(timezone.utc),
        published_at=datetime.now(timezone.utc),
    )


def test_customs_risk_article_scores_above_generic_trade_news() -> None:
    review = {
        "confidence": 90,
        "completeness_score": 92,
        "customs_value_score": 95,
        "topic_relevance_score": 88,
    }
    customs_item = _item(
        "中国海关加强出口管制风险防控",
        "中国海关针对两用物项出口管制、走私风险和申报监管开展专项核查，"
        "相关措施将影响对华贸易企业的通关与供应链安排。" * 8,
        review,
    )
    generic_item = _item(
        "国际消费市场动态",
        "海外零售市场发布季度消费趋势，介绍品牌销售与门店经营变化。" * 8,
        review,
    )

    customs_score = score_featured_item(customs_item)
    generic_score = score_featured_item(generic_item)

    assert customs_score.qualified is True
    assert customs_score.score > generic_score.score
    assert generic_score.qualified is False


def test_featured_ids_stay_stable_when_no_new_item_reaches_top_three() -> None:
    saved = ["saved-a", "saved-b", "saved-c"]
    ranked = [
        ("saved-a", 94.0),
        ("saved-b", 91.0),
        ("saved-c", 88.0),
        ("new-low", 70.0),
    ]

    selected = choose_featured_ids(saved, ranked, available_ids=set(saved) | {"new-low"})

    assert selected == saved


def test_qualified_new_item_can_replace_the_weakest_saved_item() -> None:
    saved = ["saved-a", "saved-b", "saved-c"]
    ranked = [
        ("new-high", 97.0),
        ("saved-a", 94.0),
        ("saved-b", 91.0),
        ("saved-c", 88.0),
    ]

    selected = choose_featured_ids(saved, ranked, available_ids=set(saved) | {"new-high"})

    assert selected == ["new-high", "saved-a", "saved-b"]


def test_persisted_featured_selection_only_changes_for_qualified_recent_content() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    now = datetime.now(timezone.utc)
    try:
        db.add(SourceConfig(id="featured-source", name="Featured", channel=SourceChannel.WEB_SCRAPE))
        saved_ids = ["saved-a", "saved-b", "saved-c"]
        for index, item_id in enumerate(saved_ids):
            db.add(CollectedItem(
                id=item_id, source_id="featured-source", title=f"历史重点情报 {index}",
                summary="完整摘要" * 30, content="中国海关风险管理与出口管制信息" * 40,
                collected_at=now - timedelta(days=20), published_at=now - timedelta(days=20),
            ))
        db.add(SystemConfig(id="global", featured_item_ids=saved_ids))
        db.add(CollectedItem(
            id="generic-new", source_id="featured-source", title="海外零售动态",
            summary="完整摘要" * 30, content="海外零售品牌公布门店销售趋势" * 40,
            collected_at=now, published_at=now,
        ))
        db.commit()

        unchanged = get_featured_items(db, now=now)
        assert [item.id for item in unchanged] == saved_ids

        db.add(CollectedItem(
            id="qualified-new", source_id="featured-source", title="中国海关出口管制风险预警",
            summary="完整摘要" * 30,
            content="中国海关针对两用物项出口管制、走私风险及对华贸易供应链开展监管核查。" * 40,
            raw_metadata={"quality_review": {
                "confidence": 95, "completeness_score": 95,
                "customs_value_score": 98, "topic_relevance_score": 92,
            }},
            quality_score=.9, relevance_score=.9,
            collected_at=now, published_at=now,
        ))
        db.commit()

        updated = get_featured_items(db, now=now)
        assert updated[0].id == "qualified-new"
        db.refresh(db.query(SystemConfig).filter(SystemConfig.id == "global").one())
        assert db.query(SystemConfig).filter(SystemConfig.id == "global").one().featured_item_ids[0] == "qualified-new"
    finally:
        db.close()
