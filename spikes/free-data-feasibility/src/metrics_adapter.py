from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .models import MetricResult

FORMULA_VERSION = "gt-metrics-v0.1"

REQUIRED_METRIC_DECLARATIONS = [
    ("5d_return", "percent", "5 trading days"),
    ("10d_return", "percent", "10 trading days"),
    ("20d_return", "percent", "20 trading days"),
    ("distance_to_20d_high", "percent", "20 trading days"),
    ("relative_industry_strength_5d", "percentage_point", "5 trading days"),
    ("relative_index_strength_5d", "percentage_point", "5 trading days"),
    ("volume_percentile", "percentile_0_100", "120 valid trading days"),
    ("amount_percentile", "percentile_0_100", "120 valid trading days"),
    ("turnover_rate_percentile", "percentile_0_100", "120 valid trading days"),
    ("amplitude_percentile", "percentile_0_100", "120 valid trading days"),
    ("intraday_close_position", "percent_0_100", "latest trading day"),
    ("max_intraday_drawdown", "percent", "minute close sequence"),
]


@dataclass(frozen=True)
class PreparedDaily:
    frame: pd.DataFrame
    missing_reason: str | None = None


def numeric_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    result = frame.copy()
    for column in columns:
        if column in result.columns:
            result[column] = pd.to_numeric(result[column], errors="coerce")
    return result


def sort_by_trade_date(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "trade_date" not in frame.columns:
        return frame.copy()
    return frame.copy().sort_values("trade_date").reset_index(drop=True)


def prepare_adjusted_daily(daily: pd.DataFrame) -> PreparedDaily:
    required = {"trade_date", "open", "high", "low", "close", "pre_close", "volume", "amount"}
    missing = sorted(required - set(daily.columns))
    if missing:
        return PreparedDaily(pd.DataFrame(), f"daily missing fields: {', '.join(missing)}")
    sorted_daily = sort_by_trade_date(daily)
    frame = numeric_columns(sorted_daily, ["open", "high", "low", "close", "pre_close", "volume", "amount", "turnover_rate", "amplitude"])
    for column in ["open", "high", "low", "close"]:
        frame[f"qfq_{column}"] = frame[column]
    if "amplitude" not in frame.columns or frame["amplitude"].isna().all():
        frame["amplitude"] = (frame["high"] - frame["low"]) / frame["pre_close"] * 100
    frame["close_position"] = np.where(
        (frame["high"] - frame["low"]) == 0,
        np.nan,
        (frame["close"] - frame["low"]) / (frame["high"] - frame["low"]),
    )
    return PreparedDaily(frame)


def return_rate(frame: pd.DataFrame, window: int, price_column: str = "qfq_close") -> tuple[float | None, str | None]:
    if price_column not in frame.columns:
        return None, f"{price_column} missing"
    valid = frame.dropna(subset=[price_column])
    if len(valid) < window + 1:
        return None, f"need {window + 1} rows, got {len(valid)}"
    current = valid[price_column].iloc[-1]
    previous = valid[price_column].iloc[-window - 1]
    if previous == 0 or pd.isna(previous):
        return None, "previous price is invalid"
    return float(current / previous - 1), None


def distance_to_20d_high(frame: pd.DataFrame) -> tuple[float | None, str | None]:
    if "qfq_close" not in frame.columns or "qfq_high" not in frame.columns:
        return None, "qfq close/high missing"
    valid = frame.dropna(subset=["qfq_close", "qfq_high"])
    if len(valid) < 20:
        return None, f"need 20 rows, got {len(valid)}"
    recent = valid.tail(20)
    high = recent["qfq_high"].max()
    if high == 0 or pd.isna(high):
        return None, "20d high is invalid"
    return float(valid["qfq_close"].iloc[-1] / high - 1), None


def percentile_rank(series: pd.Series, current_value: float | None = None) -> tuple[float | None, str | None]:
    valid = pd.to_numeric(series, errors="coerce").dropna()
    if valid.empty:
        return None, "series has no valid values"
    current = valid.iloc[-1] if current_value is None else current_value
    if current is None or pd.isna(current):
        return None, "current value is missing"
    lower = (valid < current).sum()
    equal = (valid == current).sum()
    return float((lower + 0.5 * equal) / len(valid) * 100), None


def percentile_window(frame: pd.DataFrame, column: str, window: int) -> tuple[float | None, str | None]:
    if column not in frame.columns:
        return None, f"{column} missing"
    valid = pd.to_numeric(frame[column], errors="coerce").dropna()
    if len(valid) < window:
        return None, f"need {window} valid rows, got {len(valid)}"
    return percentile_rank(valid.tail(window))


def latest_close_position(frame: pd.DataFrame) -> tuple[float | None, str | None]:
    if frame.empty:
        return None, "daily is empty"
    latest = frame.iloc[-1]
    if pd.isna(latest.get("high")) or pd.isna(latest.get("low")) or pd.isna(latest.get("close")):
        return None, "latest OHLC is missing"
    if latest["high"] == latest["low"]:
        return None, "high equals low"
    return float((latest["close"] - latest["low"]) / (latest["high"] - latest["low"]) * 100), None


def max_intraday_drawdown(minute_close: pd.Series | list[float] | None) -> tuple[float | None, str | None]:
    if minute_close is None:
        return None, "NOT_AVAILABLE_WITH_DAILY_DATA"
    closes = pd.to_numeric(pd.Series(minute_close), errors="coerce").dropna()
    if closes.empty:
        return None, "minute close series is empty"
    peak = closes.cummax()
    drawdowns = closes / peak - 1
    return float(drawdowns.min()), None


def relative_strength(stock_frame: pd.DataFrame, benchmark_frame: pd.DataFrame | None, window: int = 5) -> tuple[float | None, str | None]:
    stock_ret, stock_reason = return_rate(stock_frame, window, "qfq_close")
    if stock_ret is None:
        return None, f"stock return unavailable: {stock_reason}"
    if benchmark_frame is None or benchmark_frame.empty:
        return None, "benchmark missing"
    benchmark_sorted = sort_by_trade_date(benchmark_frame)
    benchmark_sorted = numeric_columns(benchmark_sorted, ["close"])
    benchmark_ret, benchmark_reason = return_rate(benchmark_sorted, window, "close")
    if benchmark_ret is None:
        return None, f"benchmark return unavailable: {benchmark_reason}"
    return float(stock_ret - benchmark_ret), None


def metric_result(
    *,
    provider: str,
    symbol: str,
    metric: str,
    value: float | None,
    unit: str,
    input_sources: list[str],
    window: str,
    as_of_date: str | None,
    missing_reason: str | None,
    status: str | None = None,
) -> MetricResult:
    metric_status = status or ("PASS" if value is not None else "DATA_INSUFFICIENT")
    return MetricResult(
        provider=provider,
        symbol=symbol,
        metric=metric,
        value=value,
        unit=unit,
        formula_version=FORMULA_VERSION,
        input_sources=input_sources,
        window=window,
        as_of_date=as_of_date,
        status=metric_status,  # type: ignore[arg-type]
        missing_reason=missing_reason,
    )


def compute_metric_suite(
    *,
    provider: str,
    symbol: str,
    daily: pd.DataFrame,
    benchmark_index: pd.DataFrame | None,
    industry_index: pd.DataFrame | None,
    minute_close: pd.Series | list[float] | None,
    percentile_size: int,
    upstream_status: str | None = None,
) -> list[MetricResult]:
    if upstream_status and upstream_status not in {"PASS", "PARTIAL_PASS"}:
        return [
            metric_result(
                provider=provider,
                symbol=symbol,
                metric=name,
                value=None,
                unit=unit,
                input_sources=[f"{provider} upstream"],
                window=window,
                as_of_date=None,
                missing_reason=f"upstream status={upstream_status}",
                status="UPSTREAM_ERROR",
            )
            for name, unit, window in REQUIRED_METRIC_DECLARATIONS
        ]

    prepared = prepare_adjusted_daily(daily)
    frame = prepared.frame
    as_of_date = None if frame.empty or "trade_date" not in frame.columns else str(frame["trade_date"].iloc[-1])
    if prepared.missing_reason and frame.empty:
        return [
            metric_result(
                provider=provider,
                symbol=symbol,
                metric=name,
                value=None,
                unit=unit,
                input_sources=[f"{provider} daily adjusted"],
                window=window,
                as_of_date=as_of_date,
                missing_reason=prepared.missing_reason,
                status="DATA_INSUFFICIENT",
            )
            for name, unit, window in REQUIRED_METRIC_DECLARATIONS
        ]

    results: list[MetricResult] = []
    for window in [5, 10, 20]:
        value, reason = return_rate(frame, window)
        results.append(
            metric_result(
                provider=provider,
                symbol=symbol,
                metric=f"{window}d_return",
                value=None if value is None else value * 100,
                unit="percent",
                input_sources=[f"{provider} adjusted daily close"],
                window=f"{window} trading days",
                as_of_date=as_of_date,
                missing_reason=reason,
            )
        )

    value, reason = distance_to_20d_high(frame)
    results.append(
        metric_result(
            provider=provider,
            symbol=symbol,
            metric="distance_to_20d_high",
            value=None if value is None else value * 100,
            unit="percent",
            input_sources=[f"{provider} adjusted daily close/high"],
            window="20 trading days",
            as_of_date=as_of_date,
            missing_reason=reason,
        )
    )

    value, reason = relative_strength(frame, industry_index, 5)
    results.append(
        metric_result(
            provider=provider,
            symbol=symbol,
            metric="relative_industry_strength_5d",
            value=None if value is None else value * 100,
            unit="percentage_point",
            input_sources=[f"{provider} adjusted daily", f"{provider} industry board history"],
            window="5 trading days",
            as_of_date=as_of_date,
            missing_reason=reason,
        )
    )

    value, reason = relative_strength(frame, benchmark_index, 5)
    results.append(
        metric_result(
            provider=provider,
            symbol=symbol,
            metric="relative_index_strength_5d",
            value=None if value is None else value * 100,
            unit="percentage_point",
            input_sources=[f"{provider} adjusted daily", f"{provider} index history"],
            window="5 trading days",
            as_of_date=as_of_date,
            missing_reason=reason,
        )
    )

    percentile_inputs = [
        ("volume_percentile", "volume", f"{provider} daily volume"),
        ("amount_percentile", "amount", f"{provider} daily amount"),
        ("turnover_rate_percentile", "turnover_rate", f"{provider} daily turnover_rate"),
        ("amplitude_percentile", "amplitude", "computed from daily OHLC/pre_close or provider amplitude"),
    ]
    for metric_name, column, source in percentile_inputs:
        value, reason = percentile_window(frame, column, percentile_size)
        results.append(
            metric_result(
                provider=provider,
                symbol=symbol,
                metric=metric_name,
                value=value,
                unit="percentile_0_100",
                input_sources=[source],
                window=f"{percentile_size} valid trading days",
                as_of_date=as_of_date,
                missing_reason=reason,
            )
        )

    value, reason = latest_close_position(frame)
    results.append(
        metric_result(
            provider=provider,
            symbol=symbol,
            metric="intraday_close_position",
            value=value,
            unit="percent_0_100",
            input_sources=[f"{provider} daily OHLC"],
            window="latest trading day",
            as_of_date=as_of_date,
            missing_reason=reason,
        )
    )

    value, reason = max_intraday_drawdown(minute_close)
    results.append(
        metric_result(
            provider=provider,
            symbol=symbol,
            metric="max_intraday_drawdown",
            value=None if value is None else value * 100,
            unit="percent",
            input_sources=[f"{provider} minute close"],
            window="current trading day minute close sequence",
            as_of_date=as_of_date,
            missing_reason=reason,
            status="NOT_AVAILABLE_WITH_DAILY_DATA" if reason == "NOT_AVAILABLE_WITH_DAILY_DATA" else None,
        )
    )
    return results
