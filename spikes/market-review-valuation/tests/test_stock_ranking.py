from __future__ import annotations

from src.stock_ranking import rank_stocks_within_board

from conftest import make_daily


def test_stock_ranking_has_role_suggestion_and_risk_penalties() -> None:
    rows = rank_stocks_within_board(
        board_id="standard_industry:test",
        board_name="test",
        stock_frames={
            "600001.SH": make_daily("600001.SH", multiplier=1.02, amount=90_000_000),
            "430001.BJ": make_daily("430001.BJ", multiplier=1.005, amount=5_000_000, suspended=True),
        },
        board_return_5d=5.0,
        index_return_5d=1.0,
        events_by_symbol={"600001.SH": 2, "430001.BJ": 0},
    )

    assert rows[0]["rank_in_board"] == 1
    assert rows[0]["role_suggestion"]["is_system_suggestion"] is True
    assert rows[0]["role_suggestion"]["user_can_correct"] is True
    weak = next(row for row in rows if row["symbol"] == "430001.BJ")
    assert {item["type"] for item in weak["risk_penalties"]} >= {"suspended", "low_liquidity", "bse_sample"}
    assert weak["score"] < rows[0]["score"]
