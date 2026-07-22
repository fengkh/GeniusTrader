from __future__ import annotations

import pytest

from src.watch_candidates import _safe_text, generate_watch_candidates


def test_watch_candidates_are_observation_only() -> None:
    result = generate_watch_candidates(
        board_rankings=[
            {
                "board_id": "standard_industry:test",
                "board_name": "test",
                "rank": 1,
                "board_stage": "accelerating",
                "heat_score": 80,
                "data_completeness": 95,
            }
        ],
        stock_rankings_by_board={
            "standard_industry:test": [
                {
                    "symbol": "600001.SH",
                    "rank_in_board": 1,
                    "status": "PASS",
                    "score": 70,
                    "metrics": {"relative_board_strength": 2.5},
                    "role_suggestion": {"role": "leader_candidate"},
                    "risk_penalties": [],
                    "data_completeness": 90,
                }
            ]
        },
    )

    assert result["candidate_type"] == "next_day_observation"
    assert "not trading instructions" in result["boundary"]
    assert result["boards"]
    assert result["stocks"]


def test_candidate_text_rejects_trading_language() -> None:
    with pytest.raises(ValueError):
        _safe_text("buy this stock")
