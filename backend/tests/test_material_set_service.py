from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.material_set_service import create_material_set, record_handoff_run
from app.models import Topic


def _session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_material_set_reuses_identical_immutable_snapshot_and_tracks_each_handoff():
    db = _session()
    db.add(Topic(id="topic-1", name="境外案件"))
    db.commit()
    items = [SimpleNamespace(id="item-1"), SimpleNamespace(id="item-2")]

    first = create_material_set(
        db,
        items,
        name="境外案件素材集",
        topic_id="topic-1",
        source_type="selection",
    )
    repeated = create_material_set(
        db,
        list(reversed(items)),
        name="再次分析",
        topic_id="topic-1",
        source_type="selection",
    )
    run_one = record_handoff_run(
        db, first, "ymg_deep", "started", remote_session_id="session-1"
    )
    run_two = record_handoff_run(
        db, first, "ymg_deep", "started", remote_session_id="session-2"
    )

    assert repeated.id == first.id
    assert first.item_ids == ["item-1", "item-2"]
    assert run_one.id != run_two.id
    assert run_one.material_set_id == first.id
    assert run_two.remote_session_id == "session-2"
