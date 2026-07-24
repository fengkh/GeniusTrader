from __future__ import annotations

from collections import defaultdict


def capability_matrix(results: list[dict]) -> dict[str, dict[str, str]]:
    matrix: dict[str, dict[str, str]] = defaultdict(dict)
    for result in results:
        matrix[result["provider"]][result["capability"]] = result["status"]
    return dict(matrix)


def success_rate(results: list[dict]) -> float:
    if not results:
        return 0.0
    passed = sum(1 for result in results if result["status"] in {"PASS", "PARTIAL"})
    return passed / len(results)
