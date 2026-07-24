from __future__ import annotations

from datetime import UTC, datetime, timedelta

from ..models import ProviderCursor


def build_cursor(provider: str, capability: str, records: list[dict], *, overlap_seconds: int = 86_400) -> ProviderCursor:
    ordered = sorted(
        [record for record in records if record.get("published_at")],
        key=lambda item: (item["published_at"], item.get("provider_announcement_id") or item.get("provider_item_id") or ""),
    )
    last = ordered[-1] if ordered else {}
    return ProviderCursor(
        provider=provider,
        capability=capability,
        cursor_type="published_at_plus_provider_id_with_overlap",
        cursor_value=f"{last.get('published_at')}|{last.get('provider_announcement_id') or last.get('provider_item_id') or ''}",
        last_success_at=datetime.now(UTC),
        last_item_published_at=datetime.fromisoformat(last["published_at"]) if last.get("published_at") else None,
        last_provider_item_id=last.get("provider_announcement_id") or last.get("provider_item_id"),
        overlap_window_seconds=overlap_seconds,
        metadata={"record_count": len(records), "requires_overlap": True},
    )


def apply_overlap_start(last_published_at: datetime, overlap_seconds: int) -> datetime:
    return last_published_at - timedelta(seconds=overlap_seconds)


def merge_incremental(existing_keys: set[str], incoming: list[dict]) -> tuple[list[dict], set[str]]:
    new_records: list[dict] = []
    keys = set(existing_keys)
    for record in incoming:
        key = record.get("deduplication_key") or record.get("provider_announcement_id") or record.get("provider_item_id")
        if not key or key in keys:
            continue
        keys.add(key)
        new_records.append(record)
    return new_records, keys
