from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from app.core.config import settings


APP_TIMEZONE = ZoneInfo(settings.APP_TIMEZONE)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def app_today() -> date:
    return utc_now().astimezone(APP_TIMEZONE).date()


def utc_day_bounds(day: date) -> tuple[datetime, datetime]:
    local_start = datetime.combine(day, time.min, tzinfo=APP_TIMEZONE)
    return (
        local_start.astimezone(timezone.utc),
        (local_start + timedelta(days=1)).astimezone(timezone.utc),
    )
