from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.time_utils import beijing_day_bounds_utc


def test_beijing_day_bounds_are_expressed_in_utc() -> None:
    now = datetime(2026, 7, 26, 1, 30, tzinfo=timezone.utc)

    start, end = beijing_day_bounds_utc(now=now)

    assert start == datetime(2026, 7, 25, 16, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 7, 26, 16, 0, tzinfo=timezone.utc)


def test_beijing_day_bounds_support_previous_days() -> None:
    now = datetime(2026, 7, 26, 18, 0, tzinfo=timezone.utc)

    start, end = beijing_day_bounds_utc(day_offset=-2, now=now)

    assert start == datetime(2026, 7, 24, 16, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 7, 25, 16, 0, tzinfo=timezone.utc)
