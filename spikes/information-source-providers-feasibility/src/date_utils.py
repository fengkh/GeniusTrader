from __future__ import annotations

from datetime import UTC, datetime, timezone
from zoneinfo import ZoneInfo


CN_TZ = ZoneInfo("Asia/Shanghai")


def parse_datetime(value: str | int | float | None, *, default_tz: timezone = CN_TZ) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, int | float):
        if value > 10_000_000_000:
            value = value / 1000
        return datetime.fromtimestamp(value, UTC).astimezone(default_tz)
    text = str(value).strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d"):
        try:
            parsed = datetime.strptime(text, fmt)
            return parsed.replace(tzinfo=default_tz)
        except ValueError:
            continue
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=default_tz)


def effective_date(value: datetime | None) -> str | None:
    return value.astimezone(CN_TZ).date().isoformat() if value else None
