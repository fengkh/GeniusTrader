from __future__ import annotations


def latency_summary(results: list[dict]) -> dict[str, float | int | None]:
    values = [int(result["latency_ms"]) for result in results if result.get("latency_ms") is not None]
    if not values:
        return {"min_ms": None, "max_ms": None, "avg_ms": None, "count": 0}
    return {"min_ms": min(values), "max_ms": max(values), "avg_ms": round(sum(values) / len(values), 2), "count": len(values)}
