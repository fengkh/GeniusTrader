from __future__ import annotations

from typing import Any

FORMULA_VERSION = "gt-watch-candidates-v0.1"

BANNED_WORDS = {"buy", "sell", "position", "target price", "must rise", "guaranteed return", "买入", "卖出", "仓位", "止盈", "止损"}


def _safe_text(text: str) -> str:
    lowered = text.lower()
    for word in BANNED_WORDS:
        if word.lower() in lowered:
            raise ValueError(f"banned trading instruction found in generated candidate text: {word}")
    return text


def generate_watch_candidates(
    *,
    board_rankings: list[dict[str, Any]],
    stock_rankings_by_board: dict[str, list[dict[str, Any]]],
    max_boards: int = 5,
    max_stocks_per_board: int = 3,
) -> dict[str, Any]:
    selected_boards = []
    selected_stocks = []
    allowed_stages = {"new_start", "accelerating", "sustained_strong", "repair"}
    for board in board_rankings:
        if len(selected_boards) >= max_boards:
            break
        if board.get("board_stage") not in allowed_stages:
            continue
        selected_boards.append(_board_candidate(board))
        for stock in stock_rankings_by_board.get(board["board_id"], [])[:max_stocks_per_board]:
            if stock.get("status") != "PASS":
                continue
            selected_stocks.append(_stock_candidate(board, stock))
    return {
        "formula_version": FORMULA_VERSION,
        "candidate_type": "next_day_observation",
        "boards": selected_boards,
        "stocks": selected_stocks,
        "boundary": "Observation candidates are generated from program rankings only. They are not trading instructions, recommendations, position sizing or return promises.",
    }


def _board_candidate(board: dict[str, Any]) -> dict[str, Any]:
    score = board.get("heat_score")
    stage = board.get("board_stage")
    reason = _safe_text(
        f"Board rank {board.get('rank')} with stage {stage}; heat score is {score} and data completeness is {board.get('data_completeness')}."
    )
    return {
        "board_id": board.get("board_id"),
        "board_name": board.get("board_name"),
        "rank": board.get("rank"),
        "current_stage": stage,
        "inclusion_reason": reason,
        "continuation_conditions": [
            _safe_text("Rising ratio remains above the configured observation floor."),
            _safe_text("Relative index strength remains positive or stops weakening."),
            _safe_text("Leader strength remains visible in program-calculated ranking."),
        ],
        "invalidation_conditions": [
            _safe_text("Board heat score falls below the configured observation floor."),
            _safe_text("Rising ratio drops sharply while turnover percentile stays elevated."),
            _safe_text("Core data fields become unavailable or stale."),
        ],
        "verification_items": [
            "Confirm board membership source and update time.",
            "Check whether related announcements or official information exist.",
        ],
        "data_completeness": board.get("data_completeness"),
    }


def _stock_candidate(board: dict[str, Any], stock: dict[str, Any]) -> dict[str, Any]:
    metrics = stock.get("metrics", {})
    reason = _safe_text(
        f"Stock rank {stock.get('rank_in_board')} in {board.get('board_name')}; score {stock.get('score')} with relative board strength {metrics.get('relative_board_strength')}."
    )
    return {
        "symbol": stock.get("symbol"),
        "board_id": board.get("board_id"),
        "board_name": board.get("board_name"),
        "rank_in_board": stock.get("rank_in_board"),
        "role_suggestion": stock.get("role_suggestion"),
        "inclusion_reason": reason,
        "continuation_conditions": [
            _safe_text("Relative board strength remains non-negative."),
            _safe_text("Data completeness remains sufficient for the same formula version."),
            _safe_text("Risk penalty items do not increase."),
        ],
        "invalidation_conditions": [
            _safe_text("Suspension, ST or other abnormal status appears."),
            _safe_text("Relative board strength turns materially negative."),
            _safe_text("Required quote or board data becomes unavailable."),
        ],
        "verification_items": [
            "Check official announcement/event count behind the score.",
            "Confirm whether board membership is still current.",
        ],
        "risk_penalties": stock.get("risk_penalties", []),
        "data_completeness": stock.get("data_completeness"),
    }

