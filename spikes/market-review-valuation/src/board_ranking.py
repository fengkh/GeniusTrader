from __future__ import annotations

from typing import Any

from .board_metrics import classify_board_status

DEFAULT_WEIGHTS = {
    "return_1d": 0.10,
    "return_3d": 0.08,
    "return_5d": 0.12,
    "return_10d": 0.07,
    "relative_index_strength": 0.10,
    "rising_ratio": 0.10,
    "limit_up_count": 0.08,
    "new_high_20d_ratio": 0.08,
    "amount_percentile": 0.08,
    "liquidity": 0.05,
    "leader_strength": 0.08,
    "ranking_continuity": 0.03,
    "consecutive_rising_days": 0.03,
}

FORMULA_VERSION = "gt-board-ranking-v0.1"


def score_board(metrics: dict[str, Any], weights: dict[str, float] | None = None) -> dict[str, Any]:
    weights = weights or DEFAULT_WEIGHTS
    components = metrics.get("components", {})
    weighted = 0.0
    used_weight = 0.0
    missing = []
    details = {}
    for name, weight in weights.items():
        component = components.get(name, {})
        value = component.get("standardized_value")
        if value is None:
            missing.append(name)
            continue
        weighted += float(value) * weight
        used_weight += weight
        details[name] = {"standardized_value": float(value), "weight": weight}
    score = weighted / used_weight if used_weight else None
    completeness = used_weight / sum(weights.values()) * 100 if weights else 0
    return {
        "score": None if score is None else round(score, 4),
        "data_completeness": round(completeness, 4),
        "missing_components": missing,
        "score_components": details,
        "formula_version": FORMULA_VERSION,
    }


def rank_boards(board_metrics: list[dict[str, Any]], weights: dict[str, float] | None = None) -> list[dict[str, Any]]:
    rows = []
    for metrics in board_metrics:
        score = score_board(metrics, weights)
        row = {
            "board_id": metrics["board_id"],
            "board_name": metrics["board_name"],
            "board_type": metrics.get("board_type"),
            "as_of_date": metrics.get("as_of_date"),
            "board_stage": metrics.get("board_stage") or classify_board_status(metrics),
            "heat_score": score["score"],
            "data_completeness": score["data_completeness"],
            "missing_components": score["missing_components"],
            "components": metrics.get("components", {}),
            "formula_version": FORMULA_VERSION,
        }
        rows.append(row)
    rows.sort(
        key=lambda item: (
            item["heat_score"] is None,
            -(item["heat_score"] if item["heat_score"] is not None else -1),
            -item["data_completeness"],
            item["board_id"],
        ),
    )
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows
