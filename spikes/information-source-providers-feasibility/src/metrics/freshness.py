from __future__ import annotations

from datetime import datetime


def freshness_summary(records: list[dict]) -> dict[str, str | None]:
    timestamps = sorted(record["published_at"] for record in records if record.get("published_at"))
    return {
        "earliest_published_at": timestamps[0] if timestamps else None,
        "latest_published_at": timestamps[-1] if timestamps else None,
        "record_count_with_time": str(len(timestamps)),
    }


def detect_future_timestamps(records: list[dict], now: datetime) -> list[str]:
    future: list[str] = []
    for record in records:
        value = record.get("published_at")
        if not value:
            continue
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            continue
        if parsed > now:
            future.append(record.get("provider_announcement_id") or record.get("provider_item_id") or record.get("title") or "")
    return future
