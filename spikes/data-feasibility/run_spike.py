from __future__ import annotations

import argparse
import os
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

from src.capability import now_queried_at, synthetic_record
from src.metrics import compute_metric_suite, data_quality_checks, sort_by_trade_date
from src.models import CapabilityRecord, MetricResult, QualityIssue, SpikeContext
from src.report import write_reports
from src.tushare_provider import (
    FIELD_SETS,
    TushareProvider,
    benchmark_for_symbol,
    choose_samples,
    is_minute_probe_window,
    latest_ended_trade_date,
    shanghai_now,
    start_date_for_days,
    yyyymmdd,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GeniusTrader Tushare data feasibility spike")
    parser.add_argument("--symbols", help="Comma-separated ts_code list overriding default samples.")
    parser.add_argument("--days", type=int, default=180, help="Historical natural-day window.")
    parser.add_argument("--percentile-window", type=int, default=120, help="Valid-trading-day percentile window.")
    parser.add_argument("--skip-optional", action="store_true", help="Skip announcements, minute, news and concept probes.")
    parser.add_argument(
        "--save-samples",
        action="store_true",
        help="Save only limited sample summary. Full raw data is never saved by this script.",
    )
    parser.add_argument(
        "--output-dir",
        default="spikes/data-feasibility/output",
        help="Local report output directory. This directory is git-ignored.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    token = os.environ.get("TUSHARE_TOKEN", "").strip()
    if not token:
        print(
            "TUSHARE_TOKEN is not set. Set it in your local shell and rerun; do not write the token to files.",
            file=sys.stderr,
        )
        return 2

    now = shanghai_now()
    start_date = start_date_for_days(args.days, now)
    end_date = yyyymmdd(now)
    output_dir = Path(args.output_dir)
    provider = TushareProvider(token)

    records: list[CapabilityRecord] = []
    metrics: list[MetricResult] = []
    quality: list[QualityIssue] = []
    daily_frames: dict[str, pd.DataFrame] = {}
    daily_basic_frames: dict[str, pd.DataFrame] = {}
    adj_factor_frames: dict[str, pd.DataFrame] = {}
    industry_member_frames: dict[str, pd.DataFrame] = {}
    industry_daily_frames: dict[str, pd.DataFrame] = {}
    minute_frames: dict[str, pd.DataFrame] = {}

    trade_cal, record = provider.query(
        capability="latest ended A-share trading day and open/closed calendar",
        api_name="trade_cal",
        params={"exchange": "", "start_date": yyyymmdd(now - timedelta(days=45)), "end_date": end_date},
        fields=FIELD_SETS["trade_cal"],
        impacts_features=["data date", "refresh status", "no future data"],
        recommended_fallback="Do not assume natural day is a trading day; block real-data run until calendar is available.",
    )
    records.append(record)
    latest_trade_date = latest_ended_trade_date(trade_cal, now)

    stock_basic, record = provider.query(
        capability="stock metadata, listing status and deterministic BSE sample selection",
        api_name="stock_basic",
        params={"exchange": "", "list_status": "L"},
        fields=FIELD_SETS["stock_basic"],
        impacts_features=["watchlist add validation", "stock identity", "listing status", "standard industry"],
        recommended_fallback="Allow manual verification and mark stock metadata stale until provider is available.",
    )
    records.append(record)

    override_symbols = parse_symbols(args.symbols)
    symbols, sample_notes = choose_samples(stock_basic, override_symbols)

    context = SpikeContext(
        provider="tushare",
        queried_at=now_queried_at(),
        shanghai_now=now.isoformat(timespec="seconds"),
        latest_trade_date=latest_trade_date,
        days=args.days,
        percentile_window=args.percentile_window,
        symbols=symbols,
        skipped_optional=args.skip_optional,
    )

    if latest_trade_date is None:
        records.append(
            synthetic_record(
                capability="latest ended trading day",
                api_name="trade_cal",
                status="DATA_INSUFFICIENT",
                queried_at=now_queried_at(),
                parameters_summary={"start_date": start_date, "end_date": end_date},
                permission_or_error_message="trade_cal did not provide an ended trading day",
                impacts_features=["all market data queries"],
                recommended_fallback="Rerun after calendar permission or provider issue is resolved.",
            )
        )

    sample_summary = build_sample_summary(stock_basic, symbols, sample_notes)

    index_frames = query_index_daily(provider, records, start_date, latest_trade_date or end_date)

    for symbol in symbols:
        stock_row = find_stock_basic_row(stock_basic, symbol)
        if stock_row is None:
            records.append(
                synthetic_record(
                    capability=f"listing status validation for {symbol}",
                    api_name="stock_basic",
                    status="PASS_EMPTY",
                    queried_at=now_queried_at(),
                    parameters_summary={"ts_code": symbol},
                    impacts_features=["watchlist add validation"],
                    recommended_fallback="Show stock metadata unavailable and do not infer listing status.",
                )
            )

        daily, record = provider.query(
            capability=f"daily OHLCV for {symbol}",
            api_name="daily",
            params={"ts_code": symbol, "start_date": start_date, "end_date": latest_trade_date or end_date},
            fields=FIELD_SETS["daily"],
            impacts_features=["daily K", "returns", "amplitude", "volume/amount percentile"],
            recommended_fallback="Show latest available daily data as missing or stale; do not ask AI to fill prices.",
        )
        records.append(record)
        daily_frames[symbol] = daily

        daily_basic, record = provider.query(
            capability=f"daily basic metrics for {symbol}",
            api_name="daily_basic",
            params={"ts_code": symbol, "start_date": start_date, "end_date": latest_trade_date or end_date},
            fields=FIELD_SETS["daily_basic"],
            impacts_features=["turnover", "market cap", "turnover percentile"],
            recommended_fallback="Hide missing valuation/turnover fields and keep price data visible.",
        )
        records.append(record)
        daily_basic_frames[symbol] = daily_basic

        adj_factor, record = provider.query(
            capability=f"adjustment factor for {symbol}",
            api_name="adj_factor",
            params={"ts_code": symbol, "start_date": start_date, "end_date": latest_trade_date or end_date},
            fields=FIELD_SETS["adj_factor"],
            impacts_features=["qfq daily K", "returns", "moving averages"],
            recommended_fallback="Use unadjusted values only with explicit label, or mark qfq metrics unavailable.",
        )
        records.append(record)
        adj_factor_frames[symbol] = adj_factor

        suspend, record = provider.query(
            capability=f"suspend/resume events for {symbol}",
            api_name="suspend_d",
            params={"ts_code": symbol, "start_date": start_date, "end_date": latest_trade_date or end_date},
            fields=FIELD_SETS["suspend_d"],
            impacts_features=["stock status", "empty trading day interpretation"],
            recommended_fallback="If API is unavailable, mark suspend lifecycle as unresolved and avoid deleting history.",
        )
        if record.status == "PASS_EMPTY":
            record = normalize_suspend_empty(record)
        records.append(record)

        member, record = provider.query(
            capability=f"Shenwan industry hierarchy for {symbol}",
            api_name="index_member_all",
            params={"ts_code": symbol},
            fields=None,
            impacts_features=["standard industry board", "relative industry strength"],
            recommended_fallback="Show standard industry unavailable; do not substitute user tags or AI text.",
        )
        records.append(record)
        industry_member_frames[symbol] = member

        industry_code = industry_code_from_members(member)
        if industry_code:
            sw_daily, record = provider.query(
                capability=f"Shenwan industry daily quote for {symbol}",
                api_name="sw_daily",
                params={"ts_code": industry_code, "start_date": start_date, "end_date": latest_trade_date or end_date},
                fields=None,
                impacts_features=["relative industry strength", "industry board performance"],
                recommended_fallback="Return relative industry strength as missing; do not use index_daily as substitute.",
            )
            industry_daily_frames[symbol] = sw_daily
            records.append(record)
        else:
            records.append(
                synthetic_record(
                    capability=f"Shenwan industry daily quote for {symbol}",
                    api_name="sw_daily",
                    status="DATA_INSUFFICIENT",
                    queried_at=now_queried_at(),
                    parameters_summary={"ts_code": symbol},
                    unit_notes="Requires Shenwan industry index code from index_member_all.",
                    permission_or_error_message="No industry index code found from index_member_all.",
                    impacts_features=["relative industry strength", "industry board performance"],
                    recommended_fallback="Return relative industry strength as missing.",
                )
            )

        if not args.skip_optional:
            probe_minute(provider, records, minute_frames, symbol, trade_cal, latest_trade_date)
            probe_announcements(provider, records, symbol, latest_trade_date or end_date)
            probe_concept(provider, records, symbol)

        benchmark_code, benchmark_note = benchmark_for_symbol(symbol)
        benchmark_frame = index_frames.get(benchmark_code) if benchmark_code else None
        if benchmark_code is None:
            records.append(
                synthetic_record(
                    capability=f"benchmark index selection for {symbol}",
                    api_name="index_daily",
                    status="DATA_INSUFFICIENT",
                    queried_at=now_queried_at(),
                    parameters_summary={"ts_code": symbol},
                    permission_or_error_message=benchmark_note,
                    impacts_features=["relative index strength"],
                    recommended_fallback="Do not calculate BSE relative index strength until benchmark is confirmed.",
                )
            )

        minute_close = close_series_from_minute(minute_frames.get(symbol))
        metrics.extend(
            compute_metric_suite(
                symbol=symbol,
                daily=daily,
                daily_basic=daily_basic_frames[symbol],
                adj_factor=adj_factor,
                benchmark_index=benchmark_frame,
                industry_index=industry_daily_frames.get(symbol),
                minute_close=minute_close,
                percentile_size=args.percentile_window,
            )
        )
        quality.extend(
            data_quality_checks(
                symbol=symbol,
                daily=daily,
                daily_basic=daily_basic_frames[symbol],
                adj_factor=adj_factor,
                stock_basic_row=stock_row,
                industry_members=industry_member_frames.get(symbol),
            )
        )

    if not args.skip_optional:
        probe_news(provider, records, latest_trade_date or end_date)

    write_reports(
        output_dir=output_dir,
        context=context,
        capability_records=records,
        metric_results=metrics,
        quality_issues=quality,
        sample_summary=sample_summary,
        token=token,
    )

    print(f"Reports written to {output_dir}")
    print(f"Capability records: {len(records)}")
    print(f"Metric results: {len(metrics)}")
    print("Tushare remains a candidate provider only; review reports before any formal provider decision.")
    return 0


def parse_symbols(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def normalize_suspend_empty(record: CapabilityRecord) -> CapabilityRecord:
    return CapabilityRecord(
        **{
            **record.to_dict(),
            "permission_or_error_message": "No suspend/resume rows for this range; interpreted as no events, not provider failure.",
        }
    )


def find_stock_basic_row(stock_basic: pd.DataFrame, symbol: str) -> pd.Series | None:
    if stock_basic.empty or "ts_code" not in stock_basic.columns:
        return None
    rows = stock_basic[stock_basic["ts_code"].astype(str) == symbol]
    if rows.empty:
        return None
    return rows.iloc[0]


def build_sample_summary(stock_basic: pd.DataFrame, symbols: list[str], notes: list[str]) -> pd.DataFrame:
    rows = []
    for symbol in symbols:
        stock_row = find_stock_basic_row(stock_basic, symbol)
        row = {"ts_code": symbol, "selection_note": "; ".join(notes)}
        if stock_row is not None:
            for column in ["symbol", "market", "exchange", "list_status", "list_date", "delist_date", "industry"]:
                row[column] = stock_row.get(column)
        else:
            row["list_status"] = "UNKNOWN"
        rows.append(row)
    return pd.DataFrame(rows)


def query_index_daily(
    provider: TushareProvider,
    records: list[CapabilityRecord],
    start_date: str,
    end_date: str,
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for code, capability in [
        ("000300.SH", "CSI 300 index daily"),
        ("399006.SZ", "ChiNext index daily"),
    ]:
        frame, record = provider.query(
            capability=capability,
            api_name="index_daily",
            params={"ts_code": code, "start_date": start_date, "end_date": end_date},
            fields=FIELD_SETS["index_daily"],
            impacts_features=["relative index strength", "index comparison"],
            recommended_fallback="Return relative index strength as missing until benchmark index is available.",
        )
        records.append(record)
        frames[code] = frame
    return frames


def industry_code_from_members(frame: pd.DataFrame) -> str | None:
    if frame.empty:
        return None
    preferred_columns = ["l2_code", "l1_code", "index_code", "ts_code"]
    latest = frame
    if "is_new" in latest.columns:
        latest = latest[latest["is_new"].astype(str).isin(["1", "Y", "True", "true"])]
        if latest.empty:
            latest = frame
    for column in preferred_columns:
        if column in latest.columns:
            values = latest[column].dropna().astype(str)
            values = values[values.str.len() > 0]
            if not values.empty:
                return values.iloc[0]
    return None


def probe_minute(
    provider: TushareProvider,
    records: list[CapabilityRecord],
    minute_frames: dict[str, pd.DataFrame],
    symbol: str,
    trade_cal: pd.DataFrame,
    latest_trade_date: str | None,
) -> None:
    if not is_minute_probe_window(trade_cal):
        records.append(
            synthetic_record(
                capability=f"current-day 1MIN data for {symbol}",
                api_name="rt_min_daily",
                status="SKIPPED_TIME_WINDOW",
                queried_at=now_queried_at(),
                parameters_summary={"ts_code": symbol, "freq": "1MIN", "latest_trade_date": latest_trade_date},
                fields_requested=FIELD_SETS["rt_min_daily"],
                unit_notes="Only tested during current A-share trading-day minute-data window.",
                impacts_features=["intraday chart", "max intraday drawdown"],
                recommended_fallback="Show minute chart unavailable and keep daily K/quant metrics visible.",
            )
        )
        return

    minute, record = provider.query(
        capability=f"current-day 1MIN data for {symbol}",
        api_name="rt_min_daily",
        params={"ts_code": symbol, "freq": "1MIN"},
        fields=FIELD_SETS["rt_min_daily"],
        impacts_features=["intraday chart", "max intraday drawdown"],
        recommended_fallback="Show minute chart unavailable and keep daily K/quant metrics visible.",
    )
    minute_frames[symbol] = minute
    records.append(record)


def probe_announcements(
    provider: TushareProvider,
    records: list[CapabilityRecord],
    symbol: str,
    end_date: str,
) -> None:
    start = pd.to_datetime(end_date) - pd.Timedelta(days=30)
    frame, record = provider.query(
        capability=f"recent announcements for {symbol}",
        api_name="anns_d",
        params={"ts_code": symbol, "start_date": start.strftime("%Y%m%d"), "end_date": end_date},
        fields=FIELD_SETS["anns_d"],
        impacts_features=["announcements", "review source facts"],
        recommended_fallback="Use exchange links or user-provided announcement links if permission is unavailable.",
    )
    del frame
    records.append(record)


def probe_concept(provider: TushareProvider, records: list[CapabilityRecord], symbol: str) -> None:
    frame, record = provider.query(
        capability=f"optional concept/member relation for {symbol}",
        api_name="tdx_member",
        params={"ts_code": symbol},
        fields=None,
        impacts_features=["standard concept board", "dynamic theme candidate"],
        recommended_fallback="Keep concept/theme unavailable; do not infer from AI text without source.",
    )
    del frame
    records.append(record)


def probe_news(provider: TushareProvider, records: list[CapabilityRecord], end_date: str) -> None:
    start = pd.to_datetime(end_date) - pd.Timedelta(days=1)
    frame, record = provider.query(
        capability="optional small news permission probe",
        api_name="news",
        params={"src": "sina", "start_date": start.strftime("%Y%m%d"), "end_date": end_date},
        fields=None,
        impacts_features=["important news", "information center"],
        recommended_fallback="Use user-pasted links and authorized news source later; do not block market data spike.",
    )
    del frame
    records.append(record)


def close_series_from_minute(frame: pd.DataFrame | None) -> pd.Series | None:
    if frame is None or frame.empty:
        return None
    close_column = "close" if "close" in frame.columns else "CLOSE" if "CLOSE" in frame.columns else None
    if close_column is None:
        return None
    time_column = "trade_time" if "trade_time" in frame.columns else "time" if "time" in frame.columns else None
    if time_column:
        frame = frame.sort_values(time_column)
    return pd.to_numeric(frame[close_column], errors="coerce")


if __name__ == "__main__":
    raise SystemExit(main())
