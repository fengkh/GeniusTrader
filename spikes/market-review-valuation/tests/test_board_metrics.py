from __future__ import annotations

from src.board_metrics import classify_board_status, compute_board_metrics

from conftest import make_daily


def test_board_metrics_include_returns_percentiles_and_stage() -> None:
    members = {
        "688001.SH": make_daily("688001.SH", multiplier=1.025, amount=90_000_000),
        "300001.SZ": make_daily("300001.SZ", multiplier=1.018, amount=70_000_000),
        "000001.SZ": make_daily("000001.SZ", multiplier=0.995, amount=40_000_000),
    }
    index_frame = make_daily("000300.SH", multiplier=1.002)

    result = compute_board_metrics(
        board_id="standard_industry:semiconductor",
        board_name="semiconductor",
        board_type="standard_industry",
        member_frames=members,
        index_frame=index_frame,
        as_of_date="2026-07-22",
        previous_rank=2,
    )

    assert result["status"] == "PASS"
    assert result["components"]["return_1d"]["raw_value"] is not None
    assert result["components"]["return_5d"]["raw_value"] is not None
    assert result["components"]["rising_ratio"]["raw_value"] > 60
    assert result["components"]["amount_percentile"]["standardized_value"] is not None
    assert result["components"]["consecutive_rising_days"]["raw_value"] >= 1
    assert result["board_stage"] == classify_board_status(result)


def test_board_metrics_propagate_data_insufficient() -> None:
    result = compute_board_metrics(
        board_id="standard_industry:empty",
        board_name="empty",
        board_type="standard_industry",
        member_frames={},
    )

    assert result["status"] == "DATA_INSUFFICIENT"
    assert result["components"]["return_1d"]["missing_status"] == "DATA_INSUFFICIENT"
