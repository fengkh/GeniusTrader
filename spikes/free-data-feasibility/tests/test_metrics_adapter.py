from __future__ import annotations

import math

import pandas as pd

from src.metrics_adapter import FORMULA_VERSION, compute_metric_suite, percentile_rank


def make_daily(rows: int = 130) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=rows, freq="B").date.astype(str)
    close = pd.Series(range(10, 10 + rows), dtype=float)
    return pd.DataFrame(
        {
            "symbol": "000001.SZ",
            "trade_date": dates,
            "open": close - 0.2,
            "high": close + 1,
            "low": close - 1,
            "close": close,
            "pre_close": close - 0.5,
            "volume": range(1000, 1000 + rows),
            "amount": range(2000, 2000 + rows),
            "turnover_rate": range(1, 1 + rows),
            "adjustment": "qfq",
        }
    )


def test_metric_formula_version_matches_gt_metrics() -> None:
    assert FORMULA_VERSION == "gt-metrics-v0.1"


def test_percentile_duplicate_values_are_deterministic() -> None:
    value, reason = percentile_rank(pd.Series([1, 2, 2, 4]), current_value=2)

    assert reason is None
    assert value == 50.0


def test_metric_suite_success_and_degrade_paths() -> None:
    stock = make_daily()
    index = pd.DataFrame(
        {
            "trade_date": pd.date_range("2026-01-01", periods=130, freq="B").date.astype(str),
            "close": range(100, 230),
        }
    )

    results = compute_metric_suite(
        provider="akshare",
        symbol="000001.SZ",
        daily=stock,
        benchmark_index=index,
        industry_index=None,
        minute_close=[10, 12, 11, 13, 9],
        percentile_size=120,
    )
    by_metric = {result.metric: result for result in results}

    assert by_metric["5d_return"].status == "PASS"
    assert math.isclose(by_metric["max_intraday_drawdown"].value or 0, ((9 / 13) - 1) * 100)
    assert by_metric["relative_industry_strength_5d"].status == "DATA_INSUFFICIENT"


def test_upstream_error_propagates_to_metrics() -> None:
    results = compute_metric_suite(
        provider="efinance",
        symbol="000001.SZ",
        daily=pd.DataFrame(),
        benchmark_index=None,
        industry_index=None,
        minute_close=None,
        percentile_size=120,
        upstream_status="NETWORK_ERROR",
    )

    assert {result.status for result in results} == {"UPSTREAM_ERROR"}
