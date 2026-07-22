from __future__ import annotations

import pandas as pd

from src.comparison import common_trade_dates, compare_adjusted_return_frames, compare_daily_frames


def test_common_dates_align_across_providers() -> None:
    frames = {
        "a": pd.DataFrame({"trade_date": ["2026-07-21", "2026-07-22"]}),
        "b": pd.DataFrame({"trade_date": ["2026-07-22", "2026-07-23"]}),
    }

    assert common_trade_dates(frames) == ["2026-07-22"]


def test_ohlc_and_volume_comparison_reports_mismatch() -> None:
    frames = {
        "akshare": pd.DataFrame({"trade_date": ["2026-07-22"], "open": [10.0], "volume": [1000.0]}),
        "efinance": pd.DataFrame({"trade_date": ["2026-07-22"], "open": [10.0], "volume": [1200.0]}),
    }

    results = compare_daily_frames(symbol="000001.SZ", provider_frames=frames, fields=["open", "volume"])
    by_field = {result.field: result for result in results}

    assert by_field["open"].within_tolerance_rows == 1
    assert by_field["volume"].mismatch_rows == 1
    assert by_field["volume"].mismatch_examples[0]["provider_b_value"] == 1200.0


def test_adjusted_prices_compare_returns_not_absolute_price() -> None:
    frames = {
        "a": pd.DataFrame({"trade_date": ["1", "2", "3", "4", "5", "6"], "close": [10, 11, 12, 13, 14, 15]}),
        "b": pd.DataFrame({"trade_date": ["1", "2", "3", "4", "5", "6"], "close": [100, 110, 120, 130, 140, 150]}),
    }

    results = compare_adjusted_return_frames(symbol="000001.SZ", provider_frames=frames, windows=[5])

    assert results[0].field == "qfq_return_5d"
    assert results[0].mismatch_rows == 0
