"""Tests for authoritative tag association counts."""
from datetime import datetime, timezone
from pathlib import Path
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import Base
from app.models import CollectedItem, SourceChannel, SourceConfig, Tag, item_tags
from app.services.tag_service import refresh_tag_counts


def test_refresh_tag_counts_uses_item_tag_links_as_the_source_of_truth() -> None:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    db = sessionmaker(bind=engine)()
    try:
        db.add(SourceConfig(id="source", name="Source", channel=SourceChannel.WEB_SCRAPE))
        db.add(Tag(id="tag-risk", namespace="risk", value="risk", item_count=99))
        db.add(CollectedItem(
            id="item-1", source_id="source", title="One", collected_at=datetime.now(timezone.utc),
        ))
        db.add(CollectedItem(
            id="item-2", source_id="source", title="Two", collected_at=datetime.now(timezone.utc),
        ))
        db.commit()
        db.execute(item_tags.insert().values(item_id="item-1", tag_id="tag-risk"))
        db.commit()

        refresh_tag_counts(db)

        assert db.get(Tag, "tag-risk").item_count == 1
    finally:
        db.close()
