from __future__ import annotations


def render(cursors: list[dict]) -> str:
    lines = [
        "# Incremental Sync Report",
        "",
        "Recommended cursor shape: `published_at + provider_id + overlap_window`.",
        "",
        "| Provider | Capability | Cursor Type | Overlap Seconds | Last Item |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for cursor in cursors:
        lines.append(
            f"| {cursor['provider']} | {cursor['capability']} | {cursor['cursor_type']} | {cursor['overlap_window_seconds']} | {cursor.get('last_provider_item_id')} |"
        )
    lines += [
        "",
        "## Required Production Behavior",
        "",
        "- Always reread an overlap window.",
        "- Do not rely on exact second-level timestamps alone.",
        "- Same-time multiple items must be ordered by stable provider ID.",
        "- Corrections and late-published announcements require backfill windows.",
    ]
    return "\n".join(lines) + "\n"
