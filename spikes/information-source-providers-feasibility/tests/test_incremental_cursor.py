from datetime import datetime

from src.announcement.incremental import apply_overlap_start, build_cursor, merge_incremental


def test_cursor_uses_published_at_and_provider_id():
    records = [
        {"published_at": "2026-07-24T10:00:00+08:00", "provider_announcement_id": "a", "deduplication_key": "a"},
        {"published_at": "2026-07-24T10:00:00+08:00", "provider_announcement_id": "b", "deduplication_key": "b"},
    ]
    cursor = build_cursor("cninfo", "announcement_list", records)
    assert cursor.last_provider_item_id == "b"
    assert cursor.overlap_window_seconds > 0


def test_merge_incremental_idempotent_and_overlap_safe():
    records, keys = merge_incremental({"a"}, [{"deduplication_key": "a"}, {"deduplication_key": "b"}])
    assert records == [{"deduplication_key": "b"}]
    assert keys == {"a", "b"}


def test_overlap_start_moves_backwards():
    last = datetime.fromisoformat("2026-07-24T10:00:00+08:00")
    assert apply_overlap_start(last, 60) < last
