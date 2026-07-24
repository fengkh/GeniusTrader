from __future__ import annotations


def completeness_summary(records: list[dict]) -> dict[str, int]:
    counts = {"complete": 0, "usable": 0, "partial": 0, "insufficient": 0}
    for record in records:
        counts[record.get("data_completeness", "insufficient")] = counts.get(record.get("data_completeness", "insufficient"), 0) + 1
    return counts


def missing_field_counts(records: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in records:
        for field in record.get("missing_fields", []):
            counts[field] = counts.get(field, 0) + 1
    return counts
