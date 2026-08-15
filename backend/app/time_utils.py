"""Shared calendar boundaries for the product's Beijing-time interface."""
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

BEIJING_TIMEZONE = ZoneInfo("Asia/Shanghai")


def beijing_day_bounds_utc(
    *,
    day_offset: int = 0,
    now: datetime | None = None,
) -> tuple[datetime, datetime]:
    """Return a Beijing calendar day's half-open UTC interval."""
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    local_day = current.astimezone(BEIJING_TIMEZONE).date() + timedelta(days=day_offset)
    local_start = datetime.combine(local_day, datetime.min.time(), tzinfo=BEIJING_TIMEZONE)
    start = local_start.astimezone(timezone.utc)
    return start, start + timedelta(days=1)
