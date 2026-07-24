from __future__ import annotations


def exact_deduplicate(records: list[dict], key_field: str = "deduplication_key") -> list[dict]:
    seen: set[str] = set()
    result: list[dict] = []
    for record in records:
        key = record.get(key_field)
        if not key:
            key = f"{record.get('provider')}|{record.get('title')}|{record.get('source_url') or record.get('document_url')}"
        if key in seen:
            continue
        seen.add(key)
        result.append(record)
    return result
