from __future__ import annotations

import math

import pandas as pd

from src.metrics import (
    compute_metric_suite,
    distance_to_20d_high,
    latest_close_position,
    max_intraday_drawdown,
    percentile_rank,
    prepare_qfq_daily,
    relative_strength,
    return_rate,
)


def make_daily(rows: int = 130) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=rows, freq="B").strftime("%Y%m%d")
    close = pd.Series(range(10, 10 + rows), dtype=float)
    return pd.DataFrame(
        {
            "ts_code": "000001.SZ",
            "trade_date": dates,
            "open": close - 0.2,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "pre_close": close - 0.5,
            "pct_chg": 1.0,
            "vol": range(1000, 1000 + rows),
            "amount": range(2000, 2000 + rows),
        }
    )


def make_adj(rows: int = 130) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=rows, freq="B").strftime("%Y%m%d")
    return pd.DataFrame({"trade_date": dates, "adj_factor": [1.0] * rows})


def make_daily_basic(rows: int = 130) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=rows, freq="B").strftime("%Y%m%d")
    return pd.DataFrame({"trade_date": dates, "turnover_rate": range(1, 1 + rows)})


def test_return_rates_use_qfq_close() -> None:
    prepared = prepare_qfq_daily(make_daily(), make_adj()).frame

    value, reason = return_rate(prepared, 5)

    assert reason is None
    assert value == (139 / 134) - 1


def test_distance_to_20d_high_formula() -> None:
    prepared = prepare_qfq_daily(make_daily(), make_adj()).frame

    value, reason = distance_to_20d_high(prepared)

    assert reason is None
    assert value == (139 / 140) - 1


def test_percentile_handles_duplicate_values() -> None:
    value, reason = percentile_rank(pd.Series([1, 2, 2, 4]), current_value=2)

    assert reason is None
    assert value == 50.0


def test_close_position_and_high_equals_low() -> None:
    frame = pd.DataFrame({"high": [12.0], "low": [10.0], "close": [11.0]})
    value, reason = latest_close_position(frame)

    assert reason is None
    assert value == 50.0

    flat = pd.DataFrame({"high": [10.0], "low": [10.0], "close": [10.0]})
    value, reason = latest_close_position(flat)

    assert value is None
    assert reason == "high equals low"


def test_relative_strength() -> None:
    stock = prepare_qfq_daily(make_daily(), make_adj()).frame
    benchmark = pd.DataFrame(
        {
            "trade_date": pd.date_range("2026-01-01", periods=130, freq="B").strftime("%Y%m%d"),
            "close": range(100, 230),
        }
    )

    value, reason = relative_strength(stock, benchmark, 5)

    assert reason is None
    assert math.isclose(value, ((139 / 134) - 1) - ((229 / 224) - 1))


def test_max_intraday_drawdown_requires_minute_data() -> None:
    value, reason = max_intraday_drawdown([10, 12, 11, 13, 9])

    assert reason is None
    assert math.isclose(value, (9 / 13) - 1)

    value, reason = max_intraday_drawdown(None)

    assert value is None
    assert reason == "NOT_AVAILABLE_WITH_DAILY_DATA"


def test_metric_suite_marks_data_insufficient() -> None:
    results = compute_metric_suite(
        symbol="000001.SZ",
        daily=make_daily(10),
        daily_basic=make_daily_basic(10),
        adj_factor=make_adj(10),
        benchmark_index=None,
        industry_index=None,
        minute_close=None,
        percentile_size=120,
    )

    by_metric = {result.metric: result for result in results}
    assert by_metric["20d_return"].status == "DATA_INSUFFICIENT"
    assert by_metric["volume_percentile"].status == "DATA_INSUFFICIENT"
    assert by_metric["max_intraday_drawdown"].status == "NOT_AVAILABLE_WITH_DAILY_DATA"
