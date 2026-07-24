from __future__ import annotations


def render(exact_count: int, near_pairs: list[tuple[int, int, float]], event_groups: list[dict]) -> str:
    lines = [
        "# Deduplication Report",
        "",
        f"- Exact unique records: {exact_count}",
        f"- Near duplicate pairs: {len(near_pairs)}",
        f"- Event groups: {len(event_groups)}",
        "",
        "## Notes",
        "",
        "- Reposts are not independent confirmations.",
        "- Corrections must not be merged away as duplicates.",
        "- Attachments and parent announcements need explicit relation fields.",
    ]
    return "\n".join(lines) + "\n"
