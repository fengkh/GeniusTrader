from __future__ import annotations

import argparse
import importlib.metadata
import platform
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd

SPIKE_ROOT = Path(__file__).resolve().parent
if str(SPIKE_ROOT) not in sys.path:
    sys.path.insert(0, str(SPIKE_ROOT))

from src.capability import now_shanghai  # noqa: E402
from src.comparison import compare_adjusted_return_frames, compare_daily_frames  # noqa: E402
from src.metrics_adapter import compute_metric_suite  # noqa: E402
from src.models import CapabilityRecord, MetricResult, QualityIssue, RunManifest, StabilityRunResult  # noqa: E402
from src.normalization import amount_volume_reasonableness, normalize_symbol, select_bse_symbol_from_snapshot  # noqa: E402
from src.providers.akshare_provider import AKSHARE_FUNCTIONS, AKShareProvider  # noqa: E402
from src.providers.baostock_provider import BAOSTOCK_FUNCTIONS, BaoStockProvider  # noqa: E402
from src.providers.efinance_provider import EFINANCE_FUNCTIONS, EFinanceProvider  # noqa: E402
from src.report import write_reports  # noqa: E402

DOCUMENTATION_SOURCES = [
    {
        "provider": "akshare",
        "title": "AKShare stock/index official documentation",
        "url": "https://akshare.akfamily.xyz/data/stock/stock.html",
    },
    {
        "provider": "efinance",
        "title": "efinance official GitHub README",
        "url": "https://github.com/Micro-sheep/efinance",
    },
    {
        "provider": "baostock",
        "title": "BaoStock Python API documentation and package page",
        "url": "https://pypi.org/project/baostock/",
    },
]

INDEX_SAMPLES = ["000300.SH", "399006.SZ"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run free data provider feasibility spike.")
    parser.add_argument("--providers", default="akshare,efinance,baostock")
    parser.add_argument("--symbols", default="600519,000001,300750,688981")
    parser.add_argument("--days", type=int, default=220)
    parser.add_argument("--percentile-window", type=int, default=120)
    parser.add_argument("--skip-minute", action="store_true")
    parser.add_argument("--skip-boards", action="store_true")
    parser.add_argument("--skip-announcements", action="store_true")
    parser.add_argument("--stability-runs", type=int, default=3)
    parser.add_argument("--request-interval", type=float, default=1.0)
    parser.add_argument("--output-dir", default=str(SPIKE_ROOT / "output"))
    parser.add_argument("--save-samples", action="store_true")
    return parser.parse_args()


def make_providers(names: list[str], request_interval: float) -> list[Any]:
    factories = {
        "akshare": AKShareProvider,
        "efinance": EFinanceProvider,
        "baostock": BaoStockProvider,
    }
    providers = []
    for name in names:
        if name not in factories:
            raise ValueError(f"Unsupported provider: {name}")
        providers.append(factories[name](request_interval=request_interval))
    return providers


def main() -> int:
    args = parse_args()
    provider_names = [item.strip().lower() for item in args.providers.split(",") if item.strip()]
    symbols = [normalize_symbol(item.strip()) or item.strip() for item in args.symbols.split(",") if item.strip()]
    end_date = pd.Timestamp.now(tz="Asia/Shanghai").date()
    start_date = end_date - pd.Timedelta(days=args.days)

    providers = make_providers(provider_names, args.request_interval)
    capability_records: list[CapabilityRecord] = []
    stability_results: list[StabilityRunResult] = []
    metric_results: list[MetricResult] = []
    quality_issues: list[QualityIssue] = []
    sample_rows: list[dict[str, Any]] = []
    daily_unadjusted: dict[str, dict[str, pd.DataFrame]] = {}
    daily_adjusted: dict[str, dict[str, pd.DataFrame]] = {}
    index_history: dict[str, dict[str, pd.DataFrame]] = {}
    minute_close: dict[tuple[str, str], pd.Series] = {}

    try:
        signatures = collect_signatures(providers)
        package_versions = collect_versions()

        for provider in providers:
            health = provider.health_check()
            capability_records.append(health.record)
            sample_rows.append(sample_row(health.record))

        symbols = ensure_bse_sample(providers, symbols, capability_records, sample_rows)

        for provider in providers:
            provider_daily_unadjusted: dict[str, pd.DataFrame] = {}
            provider_daily_adjusted: dict[str, pd.DataFrame] = {}
            provider_index: dict[str, pd.DataFrame] = {}

            universe = provider.get_stock_universe()
            record(capability_records, sample_rows, universe.record)
            pause(args.request_interval)

            snapshot = provider.get_stock_snapshot(symbols)
            record(capability_records, sample_rows, snapshot.record)
            pause(args.request_interval)

            for index_code in INDEX_SAMPLES:
                index_result = provider.get_index_history(index_code, start_date.isoformat(), end_date.isoformat())
                record(capability_records, sample_rows, index_result.record)
                if index_result.record.status in {"PASS", "PARTIAL_PASS"}:
                    provider_index[index_code] = index_result.data
                pause(args.request_interval)

            board_sample: str | None = None
            if not args.skip_boards:
                industry_boards = provider.get_industry_boards()
                record(capability_records, sample_rows, industry_boards.record)
                if not industry_boards.data.empty and "board_id" in industry_boards.data.columns:
                    board_sample = str(industry_boards.data["board_id"].dropna().iloc[0])
                pause(args.request_interval)

                concept_boards = provider.get_concept_boards()
                record(capability_records, sample_rows, concept_boards.record)
                pause(args.request_interval)

                if board_sample:
                    board_members = provider.get_board_members(board_sample)
                    record(capability_records, sample_rows, board_members.record)
                    pause(args.request_interval)

            for symbol in symbols:
                unadjusted = provider.get_daily_history(symbol, start_date.isoformat(), end_date.isoformat(), "none")
                record(capability_records, sample_rows, unadjusted.record)
                if unadjusted.record.status in {"PASS", "PARTIAL_PASS"}:
                    provider_daily_unadjusted[symbol] = unadjusted.data
                    quality_issues.extend(data_quality_checks(provider.provider_name, symbol, unadjusted.data))
                pause(args.request_interval)

                adjusted = provider.get_daily_history(symbol, start_date.isoformat(), end_date.isoformat(), "qfq")
                record(capability_records, sample_rows, adjusted.record)
                if adjusted.record.status in {"PASS", "PARTIAL_PASS"}:
                    provider_daily_adjusted[symbol] = adjusted.data
                pause(args.request_interval)

                if not args.skip_minute:
                    minute = provider.get_minute_history(symbol, f"{end_date.isoformat()} 09:30:00", f"{end_date.isoformat()} 15:00:00", "1")
                    record(capability_records, sample_rows, minute.record)
                    if minute.record.status in {"PASS", "PARTIAL_PASS"} and "close" in minute.data.columns:
                        minute_close[(provider.provider_name, symbol)] = minute.data["close"]
                    pause(args.request_interval)

                status = provider.get_stock_status(symbol)
                record(capability_records, sample_rows, status.record)
                pause(args.request_interval)

                if not args.skip_announcements:
                    announcements = provider.get_announcements(symbol, start_date.isoformat(), end_date.isoformat())
                    record(capability_records, sample_rows, announcements.record)
                    pause(args.request_interval)

                daily_for_metrics = provider_daily_adjusted.get(symbol)
                upstream_status = None
                if daily_for_metrics is None or daily_for_metrics.empty:
                    daily_for_metrics = provider_daily_unadjusted.get(symbol, pd.DataFrame())
                    upstream_status = unadjusted.record.status if daily_for_metrics.empty else None
                benchmark = provider_index.get("000300.SH")
                if benchmark is None or benchmark.empty:
                    benchmark = provider_index.get("399006.SZ")
                metric_results.extend(
                    compute_metric_suite(
                        provider=provider.provider_name,
                        symbol=symbol,
                        daily=daily_for_metrics,
                        benchmark_index=benchmark,
                        industry_index=None,
                        minute_close=minute_close.get((provider.provider_name, symbol)),
                        percentile_size=args.percentile_window,
                        upstream_status=upstream_status,
                    )
                )

            daily_unadjusted[provider.provider_name] = provider_daily_unadjusted
            daily_adjusted[provider.provider_name] = provider_daily_adjusted
            index_history[provider.provider_name] = provider_index

        stability_results = run_stability(providers, symbols, start_date.isoformat(), end_date.isoformat(), args)
        comparison_results = build_comparisons(symbols, daily_unadjusted, daily_adjusted)

        manifest = RunManifest(
            generated_at=now_shanghai(),
            timezone="Asia/Shanghai",
            python_version=platform.python_version(),
            providers_requested=provider_names,
            symbols_requested=symbols,
            days=args.days,
            percentile_window=args.percentile_window,
            request_interval=args.request_interval,
            stability_runs=args.stability_runs,
            skipped={"minute": args.skip_minute, "boards": args.skip_boards, "announcements": args.skip_announcements},
            package_versions=package_versions,
            api_signatures=signatures,
            documentation_sources=DOCUMENTATION_SOURCES,
        )
        sample_summary = pd.DataFrame(sample_rows)
        write_reports(
            output_dir=Path(args.output_dir),
            manifest=manifest,
            capability_records=capability_records,
            stability_results=stability_results,
            comparison_results=comparison_results,
            metric_results=metric_results,
            quality_issues=quality_issues,
            sample_summary=sample_summary,
        )
        print(f"Reports written to {Path(args.output_dir).resolve()}")
        return 0
    finally:
        for provider in providers:
            provider.close()


def collect_versions() -> dict[str, str]:
    versions = {}
    for package in ["akshare", "efinance", "baostock", "pandas", "numpy", "pytest"]:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = "not-installed"
    return versions


def collect_signatures(providers: list[Any]) -> dict[str, dict[str, str]]:
    by_provider = {}
    for provider in providers:
        names = {
            "akshare": AKSHARE_FUNCTIONS,
            "efinance": EFINANCE_FUNCTIONS,
            "baostock": BAOSTOCK_FUNCTIONS,
        }.get(provider.provider_name, [])
        by_provider[provider.provider_name] = provider.signatures(names)
    return by_provider


def ensure_bse_sample(
    providers: list[Any],
    symbols: list[str],
    capability_records: list[CapabilityRecord],
    sample_rows: list[dict[str, Any]],
) -> list[str]:
    if any(symbol.endswith(".BJ") for symbol in symbols if isinstance(symbol, str)):
        return symbols
    akshare = next((provider for provider in providers if provider.provider_name == "akshare"), None)
    if akshare is None:
        return symbols
    universe = akshare.get_stock_universe()
    record(capability_records, sample_rows, universe.record)
    if universe.record.status not in {"PASS", "PARTIAL_PASS"}:
        return symbols
    symbol, reason = select_bse_symbol_from_snapshot(universe.data)
    if symbol is None:
        capability_records.append(
            CapabilityRecord(
                provider="akshare",
                provider_version=akshare.provider_version,
                capability="bse_sample_selection",
                api_name="stock_zh_a_spot_em",
                status="DATA_INSUFFICIENT",
                queried_at=now_shanghai(),
                parameters_summary={},
                fields_expected=["symbol"],
                fields_returned=list(universe.data.columns),
                row_count=0,
                earliest_date=None,
                latest_date=None,
                duration_ms=0,
                source_type="public_library",
                original_units={},
                normalized_units={},
                error_message=reason,
                impacts_features=["BSE coverage"],
                recommended_fallback="Manually provide a BSE sample symbol after provider universe is verified.",
            )
        )
        return symbols
    return symbols + [symbol]


def run_stability(providers: list[Any], symbols: list[str], start_date: str, end_date: str, args: argparse.Namespace) -> list[StabilityRunResult]:
    results: list[StabilityRunResult] = []
    first_symbol = symbols[0]
    for provider in providers:
        probes = []
        if provider.provider_name == "akshare":
            probes = [
                ("stock_snapshot", lambda p=provider: p.get_stock_snapshot(symbols)),
                ("daily_history", lambda p=provider: p.get_daily_history(first_symbol, start_date, end_date, "none")),
            ]
        elif provider.provider_name == "efinance":
            probes = [
                ("daily_history", lambda p=provider: p.get_daily_history(first_symbol, start_date, end_date, "none")),
                ("stock_snapshot", lambda p=provider: p.get_stock_snapshot(symbols)),
            ]
        elif provider.provider_name == "baostock":
            probes = [("daily_history", lambda p=provider: p.get_daily_history(first_symbol, start_date, end_date, "none"))]
        for capability, probe in probes:
            for run_index in range(1, args.stability_runs + 1):
                result = probe()
                results.append(
                    StabilityRunResult(
                        provider=provider.provider_name,
                        capability=capability,
                        api_name=result.record.api_name,
                        run_index=run_index,
                        status=result.record.status,
                        row_count=result.record.row_count,
                        fields_returned=result.record.fields_returned,
                        latest_date=result.record.latest_date,
                        duration_ms=result.record.duration_ms,
                        error_message=result.record.error_message,
                    )
                )
                if result.record.status == "RATE_LIMITED":
                    break
                pause(args.request_interval)
    return results


def build_comparisons(
    symbols: list[str],
    daily_unadjusted: dict[str, dict[str, pd.DataFrame]],
    daily_adjusted: dict[str, dict[str, pd.DataFrame]],
) -> list[Any]:
    results: list[Any] = []
    for symbol in symbols:
        unadjusted_frames = {
            provider: frames[symbol]
            for provider, frames in daily_unadjusted.items()
            if symbol in frames and not frames[symbol].empty
        }
        results.extend(compare_daily_frames(symbol=symbol, provider_frames=unadjusted_frames))
        adjusted_frames = {
            provider: frames[symbol]
            for provider, frames in daily_adjusted.items()
            if symbol in frames and not frames[symbol].empty
        }
        results.extend(compare_adjusted_return_frames(symbol=symbol, provider_frames=adjusted_frames))
    return results


def data_quality_checks(provider: str, symbol: str, daily: pd.DataFrame) -> list[QualityIssue]:
    issues: list[QualityIssue] = []

    def add(dataset: str, check_name: str, status: str, message: str, dates: list[str] | None = None) -> None:
        issues.append(
            QualityIssue(
                provider=provider,
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
    sorted_daily = daily.sort_values("trade_date") if "trade_date" in daily.columns else daily
    duplicates = sorted_daily[sorted_daily.duplicated("trade_date", keep=False)] if "trade_date" in sorted_daily.columns else pd.DataFrame()
    add("daily", "date_duplicates", "FAIL" if not duplicates.empty else "PASS", "duplicate trade_date rows found" if not duplicates.empty else "no duplicate trade_date rows", duplicates["trade_date"].astype(str).tolist()[:10] if not duplicates.empty else [])
    if {"open", "high", "low", "close"}.issubset(sorted_daily.columns):
        numeric = sorted_daily.copy()
        for column in ["open", "high", "low", "close", "volume", "amount"]:
            if column in numeric.columns:
                numeric[column] = pd.to_numeric(numeric[column], errors="coerce")
        invalid_ohlc = numeric[
            (numeric["high"] < numeric[["open", "close", "low"]].max(axis=1))
            | (numeric["low"] > numeric[["open", "close", "high"]].min(axis=1))
        ]
        add("daily", "ohlc_relation", "FAIL" if not invalid_ohlc.empty else "PASS", "invalid OHLC relation found" if not invalid_ohlc.empty else "OHLC relation valid", invalid_ohlc["trade_date"].astype(str).tolist()[:10] if not invalid_ohlc.empty and "trade_date" in invalid_ohlc else [])
    ok, reason = amount_volume_reasonableness(sorted_daily)
    add("units", "amount_volume_reasonableness", "WARN" if not ok else "PASS", reason)
    return issues


def sample_row(record: CapabilityRecord) -> dict[str, Any]:
    return {
        "provider": record.provider,
        "capability": record.capability,
        "api_name": record.api_name,
        "status": record.status,
        "row_count": record.row_count,
        "latest_date": record.latest_date,
        "duration_ms": record.duration_ms,
    }


def record(records: list[CapabilityRecord], rows: list[dict[str, Any]], capability_record: CapabilityRecord) -> None:
    records.append(capability_record)
    rows.append(sample_row(capability_record))


def pause(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)


if __name__ == "__main__":
    raise SystemExit(main())
