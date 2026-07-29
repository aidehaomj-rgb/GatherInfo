from datetime import datetime, timedelta, timezone

from app.routes.items import _format_batch_label_time


def test_batch_label_converts_naive_utc_to_beijing_time():
    value = datetime(2026, 7, 28, 19, 52)

    assert _format_batch_label_time(value) == "2026-07-29 03:52"


def test_batch_label_converts_aware_timestamp_to_beijing_time():
    eastern = timezone(timedelta(hours=-4))
    value = datetime(2026, 7, 28, 11, 50, tzinfo=eastern)

    assert _format_batch_label_time(value) == "2026-07-28 23:50"
