from __future__ import annotations

from src.board_ranking import rank_boards


def _metrics(board_id: str, score: float) -> dict[str, object]:
    return {
        "board_id": board_id,
        "board_name": board_id,
        "board_type": "standard_industry",
        "components": {
            "return_1d": {"standardized_value": score, "raw_value": score},
            "return_3d": {"standardized_value": score, "raw_value": score},
            "return_5d": {"standardized_value": score, "raw_value": score},
            "return_10d": {"standardized_value": score, "raw_value": score},
            "relative_index_strength": {"standardized_value": score, "raw_value": score},
            "rising_ratio": {"standardized_value": score, "raw_value": score},
            "limit_up_count": {"standardized_value": score, "raw_value": score},
            "new_high_20d_ratio": {"standardized_value": score, "raw_value": score},
            "amount_percentile": {"standardized_value": score, "raw_value": score},
            "liquidity": {"standardized_value": score, "raw_value": score},
            "leader_strength": {"standardized_value": score, "raw_value": score},
            "ranking_continuity": {"standardized_value": score, "raw_value": score},
            "consecutive_rising_days": {"standardized_value": score, "raw_value": score},
        },
    }


def test_board_ranking_is_deterministic_and_descending_by_score() -> None:
    ranked = rank_boards([_metrics("b", 80), _metrics("a", 80), _metrics("c", 60)])

    assert [row["board_id"] for row in ranked] == ["a", "b", "c"]
    assert [row["rank"] for row in ranked] == [1, 2, 3]
