from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_in(seconds: int) -> datetime:
    return utc_now() + timedelta(seconds=seconds)


def to_timezone(value: datetime, timezone_name: str) -> datetime:
    if value.tzinfo is None:
        raise ValueError("naive datetimes are not allowed")
    return value.astimezone(ZoneInfo(timezone_name))
