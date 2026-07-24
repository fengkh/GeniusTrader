from __future__ import annotations

from collections import defaultdict


def group_events(records: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        symbols = ",".join(sorted(record.get("stock_symbols") or record.get("related_symbols") or []))
        title = record.get("normalized_title") or record.get("title") or ""
        date = (record.get("published_at") or "")[:10]
        key = f"{symbols}|{date}|{title[:32]}"
        grouped[key].append(record)
    events: list[dict] = []
    for key, items in grouped.items():
        events.append(
            {
                "event_key": key,
                "canonical_title": items[0].get("title"),
                "source_count": len({item.get("provider") for item in items}),
                "repost_count": max(0, len(items) - len({item.get("provider") for item in items})),
                "earliest_published_at": min((item.get("published_at") for item in items if item.get("published_at")), default=None),
                "latest_published_at": max((item.get("published_at") for item in items if item.get("published_at")), default=None),
                "related_symbols": sorted({symbol for item in items for symbol in (item.get("stock_symbols") or item.get("related_symbols") or [])}),
                "confidence": "medium" if len(items) > 1 else "low",
                "clustering_reasons": ["same_symbol_date_title_prefix"],
                "item_count": len(items),
            }
        )
    return events
