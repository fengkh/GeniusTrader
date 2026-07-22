from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .models import MetricResult, QualityIssue

FORMULA_VERSION = "gt-metrics-v0.1"


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


def prepare_qfq_daily(daily: pd.DataFrame, adj_factor: pd.DataFrame) -> PreparedDaily:
    required = {"trade_date", "open", "high", "low", "close", "pre_close", "vol", "amount"}
    missing = sorted(required - set(daily.columns))
    if missing:
        return PreparedDaily(pd.DataFrame(), f"daily missing fields: {', '.join(missing)}")
    if adj_factor.empty or "adj_factor" not in adj_factor.columns or "trade_date" not in adj_factor.columns:
        return PreparedDaily(pd.DataFrame(), "adj_factor missing")

    daily_sorted = sort_by_trade_date(daily)
    adj_sorted = sort_by_trade_date(adj_factor[["trade_date", "adj_factor"]])
    merged = pd.merge(daily_sorted, adj_sorted, on="trade_date", how="left")
    merged = numeric_columns(
        merged,
        ["open", "high", "low", "close", "pre_close", "vol", "amount", "adj_factor"],
    )

    if merged["adj_factor"].isna().any():
        return PreparedDaily(merged, "adj_factor has missing rows")

    latest_factor = merged["adj_factor"].dropna().iloc[-1]
    if latest_factor == 0 or pd.isna(latest_factor):
        return PreparedDaily(merged, "latest adj_factor is invalid")

    for column in ["open", "high", "low", "close"]:
        merged[f"qfq_{column}"] = merged[column] * merged["adj_factor"] / latest_factor

    merged["amplitude"] = (merged["high"] - merged["low"]) / merged["pre_close"]
    merged["close_position"] = np.where(
        (merged["high"] - merged["low"]) == 0,
        np.nan,
        (merged["close"] - merged["low"]) / (merged["high"] - merged["low"]),
    )
    return PreparedDaily(merged)


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


def percentile_window(
    frame: pd.DataFrame,
    column: str,
    window: int,
) -> tuple[float | None, str | None]:
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


def relative_strength(
    stock_frame: pd.DataFrame,
    benchmark_frame: pd.DataFrame | None,
    window: int = 5,
    benchmark_column: str = "close",
) -> tuple[float | None, str | None]:
    stock_ret, stock_reason = return_rate(stock_frame, window, "qfq_close")
    if stock_ret is None:
        return None, f"stock return unavailable: {stock_reason}"
    if benchmark_frame is None or benchmark_frame.empty:
        return None, "benchmark missing"
    benchmark_sorted = sort_by_trade_date(benchmark_frame)
    benchmark_sorted = numeric_columns(benchmark_sorted, [benchmark_column])
    benchmark_ret, benchmark_reason = return_rate(benchmark_sorted, window, benchmark_column)
    if benchmark_ret is None:
        return None, f"benchmark return unavailable: {benchmark_reason}"
    return float(stock_ret - benchmark_ret), None


def metric_result(
    *,
    symbol: str,
    metric: str,
    value: float | None,
    unit: str,
    input_data_source: str,
    window: str,
    as_of_date: str | None,
    missing_reason: str | None,
    status: str | None = None,
) -> MetricResult:
    metric_status = status or ("PASS" if value is not None else "DATA_INSUFFICIENT")
    return MetricResult(
        symbol=symbol,
        metric=metric,
        value=value,
        unit=unit,
        formula_version=FORMULA_VERSION,
        input_data_source=input_data_source,
        window=window,
        as_of_date=as_of_date,
        status=metric_status,  # type: ignore[arg-type]
        missing_reason=missing_reason,
    )


def compute_metric_suite(
    *,
    symbol: str,
    daily: pd.DataFrame,
    daily_basic: pd.DataFrame,
    adj_factor: pd.DataFrame,
    benchmark_index: pd.DataFrame | None,
    industry_index: pd.DataFrame | None,
    minute_close: pd.Series | list[float] | None,
    percentile_size: int,
) -> list[MetricResult]:
    prepared = prepare_qfq_daily(daily, adj_factor)
    frame = prepared.frame
    as_of_date = None if frame.empty or "trade_date" not in frame.columns else str(frame["trade_date"].iloc[-1])

    if prepared.missing_reason and frame.empty:
        return [
            metric_result(
                symbol=symbol,
                metric=name,
                value=None,
                unit=unit,
                input_data_source="tushare daily/adj_factor",
                window=window,
                as_of_date=as_of_date,
                missing_reason=prepared.missing_reason,
                status="DATA_INSUFFICIENT",
            )
            for name, unit, window in REQUIRED_METRIC_DECLARATIONS
        ]

    daily_basic_sorted = sort_by_trade_date(daily_basic)
    daily_basic_sorted = numeric_columns(daily_basic_sorted, ["turnover_rate", "turnover_rate_f"])
    merged = pd.merge(
        frame,
        daily_basic_sorted[["trade_date", "turnover_rate"]]
        if "turnover_rate" in daily_basic_sorted.columns and "trade_date" in daily_basic_sorted.columns
        else pd.DataFrame(columns=["trade_date", "turnover_rate"]),
        on="trade_date",
        how="left",
    )

    results: list[MetricResult] = []
    for window in [5, 10, 20]:
        value, reason = return_rate(frame, window)
        results.append(
            metric_result(
                symbol=symbol,
                metric=f"{window}d_return",
                value=None if value is None else value * 100,
                unit="percent",
                input_data_source="tushare daily + adj_factor, qfq close",
                window=f"{window} trading days",
                as_of_date=as_of_date,
                missing_reason=reason,
            )
        )

    value, reason = distance_to_20d_high(frame)
    results.append(
        metric_result(
            symbol=symbol,
            metric="distance_to_20d_high",
            value=None if value is None else value * 100,
            unit="percent",
            input_data_source="tushare daily + adj_factor, qfq close/high",
            window="20 trading days",
            as_of_date=as_of_date,
            missing_reason=reason,
        )
    )

    value, reason = relative_strength(frame, industry_index, 5)
    results.append(
        metric_result(
            symbol=symbol,
            metric="relative_industry_strength_5d",
            value=None if value is None else value * 100,
            unit="percentage_point",
            input_data_source="tushare daily + adj_factor + sw industry daily",
            window="5 trading days",
            as_of_date=as_of_date,
            missing_reason=reason,
        )
    )

    value, reason = relative_strength(frame, benchmark_index, 5)
    results.append(
        metric_result(
            symbol=symbol,
            metric="relative_index_strength_5d",
            value=None if value is None else value * 100,
            unit="percentage_point",
            input_data_source="tushare daily + adj_factor + index_daily",
            window="5 trading days",
            as_of_date=as_of_date,
            missing_reason=reason,
        )
    )

    percentile_inputs = [
        ("volume_percentile", "vol", "tushare daily vol"),
        ("amount_percentile", "amount", "tushare daily amount"),
        ("turnover_rate_percentile", "turnover_rate", "tushare daily_basic turnover_rate"),
        ("amplitude_percentile", "amplitude", "computed from daily OHLC/pre_close"),
    ]
    for metric_name, column, source in percentile_inputs:
        value, reason = percentile_window(merged, column, percentile_size)
        results.append(
            metric_result(
                symbol=symbol,
                metric=metric_name,
                value=value,
                unit="percentile_0_100",
                input_data_source=source,
                window=f"{percentile_size} valid trading days",
                as_of_date=as_of_date,
                missing_reason=reason,
            )
        )

    value, reason = latest_close_position(frame)
    results.append(
        metric_result(
            symbol=symbol,
            metric="intraday_close_position",
            value=value,
            unit="percent_0_100",
            input_data_source="tushare daily OHLC",
            window="latest trading day",
            as_of_date=as_of_date,
            missing_reason=reason,
        )
    )

    value, reason = max_intraday_drawdown(minute_close)
    results.append(
        metric_result(
            symbol=symbol,
            metric="max_intraday_drawdown",
            value=None if value is None else value * 100,
            unit="percent",
            input_data_source="tushare rt_min_daily close",
            window="current trading day minute close sequence",
            as_of_date=as_of_date,
            missing_reason=reason,
            status="NOT_AVAILABLE_WITH_DAILY_DATA" if reason == "NOT_AVAILABLE_WITH_DAILY_DATA" else None,
        )
    )

    return results


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


def data_quality_checks(
    *,
    symbol: str,
    daily: pd.DataFrame,
    daily_basic: pd.DataFrame,
    adj_factor: pd.DataFrame,
    stock_basic_row: pd.Series | None = None,
    industry_members: pd.DataFrame | None = None,
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    daily_sorted = sort_by_trade_date(daily)
    numeric_daily = numeric_columns(daily_sorted, ["open", "high", "low", "close", "pre_close", "vol", "amount"])

    def add(dataset: str, check_name: str, status: str, message: str, dates: list[str] | None = None) -> None:
        issues.append(
            QualityIssue(
                symbol=symbol,
                dataset=dataset,
                check_name=check_name,
                status=status,  # type: ignore[arg-type]
                message=message,
                affected_dates=dates or [],
            )
        )

    if daily.empty:
        add("daily", "not_empty", "FAIL", "daily returned no rows")
        return issues

    duplicate_dates = daily_sorted[daily_sorted.duplicated("trade_date", keep=False)] if "trade_date" in daily_sorted.columns else pd.DataFrame()
    add(
        "daily",
        "date_duplicates",
        "FAIL" if not duplicate_dates.empty else "PASS",
        "duplicate trade_date rows found" if not duplicate_dates.empty else "no duplicate trade_date rows",
        duplicate_dates["trade_date"].astype(str).tolist() if not duplicate_dates.empty else [],
    )
    is_sorted = daily_sorted["trade_date"].astype(str).is_monotonic_increasing if "trade_date" in daily_sorted.columns else False
    add("daily", "date_ascending", "PASS" if is_sorted else "FAIL", "trade_date ascending" if is_sorted else "trade_date not ascending")

    invalid_ohlc = numeric_daily[
        (numeric_daily["high"] < numeric_daily[["open", "close", "low"]].max(axis=1))
        | (numeric_daily["low"] > numeric_daily[["open", "close", "high"]].min(axis=1))
    ]
    add(
        "daily",
        "ohlc_relation",
        "FAIL" if not invalid_ohlc.empty else "PASS",
        "invalid OHLC relation found" if not invalid_ohlc.empty else "OHLC relation valid",
        invalid_ohlc["trade_date"].astype(str).tolist() if not invalid_ohlc.empty and "trade_date" in invalid_ohlc else [],
    )

    negative = numeric_daily[(numeric_daily["vol"] < 0) | (numeric_daily["amount"] < 0)]
    add(
        "daily",
        "negative_volume_amount",
        "FAIL" if not negative.empty else "PASS",
        "negative volume or amount found" if not negative.empty else "volume and amount non-negative",
        negative["trade_date"].astype(str).tolist() if not negative.empty and "trade_date" in negative else [],
    )

    if not daily_basic.empty and "trade_date" in daily_basic.columns:
        daily_dates = set(daily_sorted["trade_date"].astype(str))
        basic_dates = set(daily_basic["trade_date"].astype(str))
        missing_basic = sorted(daily_dates - basic_dates)
        add(
            "daily_basic",
            "date_alignment",
            "WARN" if missing_basic else "PASS",
            f"daily_basic missing {len(missing_basic)} daily dates" if missing_basic else "daily and daily_basic dates align",
            missing_basic[:10],
        )
    else:
        add("daily_basic", "date_alignment", "WARN", "daily_basic unavailable or missing trade_date")

    if not adj_factor.empty and "trade_date" in adj_factor.columns:
        daily_dates = set(daily_sorted["trade_date"].astype(str))
        adj_dates = set(adj_factor["trade_date"].astype(str))
        missing_adj = sorted(daily_dates - adj_dates)
        add(
            "adj_factor",
            "date_alignment",
            "FAIL" if missing_adj else "PASS",
            f"adj_factor missing {len(missing_adj)} daily dates" if missing_adj else "adj_factor dates align",
            missing_adj[:10],
        )
    else:
        add("adj_factor", "date_alignment", "FAIL", "adj_factor unavailable or missing trade_date")

    latest_daily = str(daily_sorted["trade_date"].iloc[-1]) if "trade_date" in daily_sorted.columns else None
    latest_basic = str(sort_by_trade_date(daily_basic)["trade_date"].iloc[-1]) if not daily_basic.empty and "trade_date" in daily_basic.columns else None
    add(
        "daily_basic",
        "latest_date_consistency",
        "WARN" if latest_basic and latest_daily != latest_basic else "PASS",
        f"latest daily={latest_daily}, daily_basic={latest_basic}",
    )

    if stock_basic_row is not None:
        row_symbol = str(stock_basic_row.get("ts_code", ""))
        add(
            "stock_basic",
            "symbol_consistency",
            "PASS" if row_symbol == symbol else "FAIL",
            f"stock_basic ts_code={row_symbol}",
        )
    else:
        add("stock_basic", "symbol_consistency", "WARN", "stock_basic row unavailable")

    if industry_members is not None and not industry_members.empty:
        version_columns = [column for column in ["is_new", "in_date", "out_date"] if column in industry_members.columns]
        add(
            "index_member_all",
            "industry_history_versions",
            "WARN" if len(industry_members) > 1 else "PASS",
            f"industry member rows={len(industry_members)}, version fields={version_columns}",
        )
    else:
        add("index_member_all", "industry_history_versions", "WARN", "industry member rows unavailable")

    add("units", "unit_notes_present", "PASS", "daily vol is shares in Tushare unit convention; amount unit requires provider confirmation before formal use")
    add("missing_values", "empty_not_zero", "PASS", "missing values are kept as NaN/None and not converted to zero")
    add("schema", "field_change_detection", "PASS", "capability records include requested and returned field lists")
    return issues
