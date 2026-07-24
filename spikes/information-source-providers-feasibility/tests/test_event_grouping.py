from src.dedup.event_grouping import group_events


def test_event_grouping_does_not_count_reposts_as_independent():
    groups = group_events(
        [
            {"provider": "a", "title": "事件", "normalized_title": "事件", "published_at": "2026-07-24", "related_symbols": ["600519.SH"]},
            {"provider": "a", "title": "事件", "normalized_title": "事件", "published_at": "2026-07-24", "related_symbols": ["600519.SH"]},
        ]
    )
    assert groups[0]["source_count"] == 1
    assert groups[0]["repost_count"] == 1
