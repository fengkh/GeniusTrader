from __future__ import annotations

import argparse
import importlib.metadata
import json
import platform
import sys
from pathlib import Path
from typing import Any

import pandas as pd

SPIKE_ROOT = Path(__file__).resolve().parent
REPO_ROOT = SPIKE_ROOT.parents[1]
if str(SPIKE_ROOT) not in sys.path:
    sys.path.insert(0, str(SPIKE_ROOT))

from src.board_metrics import compute_board_metrics  # noqa: E402
from src.board_ranking import rank_boards  # noqa: E402
from src.financial_normalization import normalize_financial_record  # noqa: E402
from src.market_universe import probe_baostock_market_data, probe_efinance_snapshot  # noqa: E402
from src.report import write_reports  # noqa: E402
from src.stock_ranking import rank_stocks_within_board  # noqa: E402
from src.valuation_router import route_valuation  # noqa: E402
from src.watch_candidates import generate_watch_candidates  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run market review and valuation feasibility spike.")
    parser.add_argument("--output-dir", default=str(SPIKE_ROOT / "output"))
    parser.add_argument("--max-boards", type=int, default=20)
    parser.add_argument("--max-stocks-per-board", type=int, default=20)
    parser.add_argument("--days", type=int, default=160)
    parser.add_argument("--request-interval", type=float, default=0.2)
    parser.add_argument("--skip-network", action="store_true")
    parser.add_argument("--as-of-date", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    max_boards = min(max(args.max_boards, 1), 20)
    max_stocks = min(max(args.max_stocks_per_board, 1), 20)
    prior = load_prior_spike_outputs()
    provider_records: list[dict[str, Any]] = prior_provider_records(prior)
    valuation_records: list[dict[str, Any]] = []
    network_completed = False
    if args.skip_network:
        probe = synthetic_probe(args.as_of_date)
        provider_records.extend(probe["records"])
        valuation_records.extend(probe["valuation_records"])
    else:
        efinance_probe = probe_efinance_snapshot()
        provider_records.append(efinance_probe["record"])
        probe = probe_baostock_market_data(
            max_boards=max_boards,
            max_stocks_per_board=max_stocks,
            days=args.days,
            request_interval=args.request_interval,
            as_of_date=args.as_of_date,
        )
        provider_records.extend(probe["records"])
        valuation_records.extend(probe["valuation_records"])
        network_completed = bool(probe.get("network_completed")) or efinance_probe["record"].get("status") == "PASS"

    board_daily = probe.get("board_daily", {})
    if not board_daily:
        board_daily = synthetic_board_daily()
    index_frame = synthetic_index_frame()
    board_metrics = []
    for board_id, members in board_daily.items():
        board_name = board_id.split(":", 1)[1] if ":" in board_id else board_id
        board_metrics.append(
            compute_board_metrics(
                board_id=board_id,
                board_name=board_name,
                board_type="standard_industry",
                member_frames=members,
                index_frame=index_frame,
                provider="baostock_or_synthetic",
            )
        )
    board_rankings = rank_boards(board_metrics)
    stock_rankings_by_board = {}
    for board in board_rankings:
        members = board_daily.get(board["board_id"], {})
        component = (board.get("components") or {}).get("return_5d", {})
        board_ret = component.get("raw_value")
        stock_rankings_by_board[board["board_id"]] = rank_stocks_within_board(
            board_id=board["board_id"],
            board_name=board["board_name"],
            stock_frames=members,
            board_return_5d=board_ret,
            index_return_5d=2.0,
            events_by_symbol=synthetic_event_counts(members),
        )
    watch_candidates = generate_watch_candidates(board_rankings=board_rankings, stock_rankings_by_board=stock_rankings_by_board)

    financials = probe.get("valuation_financials") or synthetic_financials()
    valuations = [route_valuation(item) for item in financials[:20]]
    provider_gaps = build_provider_gaps(prior, provider_records, valuation_records)
    market_review = {
        "network_completed": network_completed if not args.skip_network else False,
        "input_scope": probe.get("market_breadth", {}).get("input_scope", "synthetic_formula_sample"),
        "market_breadth": probe.get("market_breadth"),
        "board_rankings": board_rankings,
        "watch_candidates": watch_candidates,
        "whole_market_review_conclusion": whole_market_conclusion(provider_records),
        "hot_boards_conclusion": "calculable from board-member daily histories when board membership and member daily data are available; concept-board coverage remains open.",
        "board_continuity_conclusion": "calculable when prior ranking snapshots are stored; this spike validates the component but does not freeze weights.",
        "hot_stocks_conclusion": "calculable inside validated board-member samples with raw evidence, ranks, risk penalties and update dates.",
        "watch_candidates_conclusion": "can form from program rankings and rule conditions; output is observation-only, not trading advice.",
        "free_plan_conclusion": free_plan_conclusion(prior, provider_records, valuation_records),
    }
    manifest = {
        "generated_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(),
        "timezone": "Asia/Shanghai",
        "python_version": platform.python_version(),
        "package_versions": package_versions(),
        "max_boards": max_boards,
        "max_stocks_per_board": max_stocks,
        "days": args.days,
        "request_interval": args.request_interval,
        "skip_network": args.skip_network,
        "prior_spike_outputs_loaded": sorted(prior.keys()),
        "boundary": "No provider is selected; no trading, brokerage, real AI, backend, database or task queue is created.",
    }
    write_reports(
        output_dir=Path(args.output_dir),
        manifest=manifest,
        provider_records=provider_records,
        market_review=market_review,
        board_rankings=board_rankings,
        stock_rankings_by_board=stock_rankings_by_board,
        watch_candidates=watch_candidates,
        valuation_records=valuation_records,
        valuations=valuations,
        provider_gaps=provider_gaps,
    )
    print(f"Reports written to {Path(args.output_dir).resolve()}")
    return 0


def load_prior_spike_outputs() -> dict[str, Any]:
    files = {
        "free_provider_recommendation": REPO_ROOT / "spikes/free-data-feasibility/output/provider_recommendation.json",
        "free_capability_report": REPO_ROOT / "spikes/free-data-feasibility/output/capability_report.json",
        "free_metrics_report": REPO_ROOT / "spikes/free-data-feasibility/output/metrics_report.json",
        "tushare_capability_report": REPO_ROOT / "spikes/data-feasibility/output/capability_report.json",
        "tushare_metrics_report": REPO_ROOT / "spikes/data-feasibility/output/metrics_report.json",
    }
    payload: dict[str, Any] = {}
    for key, path in files.items():
        if not path.exists():
            continue
        try:
            payload[key] = json.loads(path.read_text(encoding="utf-8"))
        except Exception as error:  # noqa: BLE001
            payload[key] = {"load_error": str(error)}
    return payload


def package_versions() -> dict[str, str]:
    result = {}
    for package in ["pandas", "numpy", "baostock", "efinance", "akshare", "pytest"]:
        try:
            result[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            result[package] = "not-installed"
    return result


def prior_provider_records(prior: dict[str, Any]) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    recommendation = prior.get("free_provider_recommendation", {}).get("answers", {})
    for provider in ["akshare", "efinance", "baostock"]:
        daily_status = _status_from_recommendation(recommendation.get("2_daily_k_stable"), provider)
        snapshot_status = _status_from_recommendation(recommendation.get("3_latest_snapshot_stable"), provider)
        board_status = _status_from_recommendation(recommendation.get("6_industry_and_concept_available"), provider)
        if daily_status:
            records.append(_prior_record(provider, "prior_free_daily_history", daily_status))
        if snapshot_status:
            records.append(_prior_record(provider, "prior_free_latest_snapshot", snapshot_status))
        if board_status:
            records.append(_prior_record(provider, "prior_free_industry_or_concept", board_status))
    if "tushare_capability_report" in prior:
        records.append(
            {
                "provider": "tushare",
                "capability": "prior_tushare_spike_loaded",
                "api_name": "spikes/data-feasibility/output/capability_report.json",
                "status": "PRIOR_RESULT_LOADED",
                "row_count": 0,
                "fields_returned": [],
                "fallback": "Review prior Tushare spike report before closing provider questions.",
            }
        )
    return records


def _prior_record(provider: str, capability: str, status: str) -> dict[str, Any]:
    return {
        "provider": provider,
        "capability": capability,
        "api_name": "spikes/free-data-feasibility/output/provider_recommendation.json",
        "status": f"PRIOR_{status}",
        "row_count": 0,
        "fields_returned": [],
        "fallback": "Prior result only; this market-review spike still performs its own bounded live probes where implemented.",
    }


def _status_from_recommendation(value: Any, provider: str) -> str | None:
    if isinstance(value, dict):
        raw = value.get(provider)
    elif isinstance(value, str):
        try:
            raw = json.loads(value).get(provider)
        except Exception:  # noqa: BLE001
            raw = None
    else:
        raw = None
    return None if raw is None else str(raw)


def whole_market_conclusion(records: list[dict[str, Any]]) -> str:
    by_capability = {(item.get("provider"), item.get("capability")): item.get("status") for item in records}
    if by_capability.get(("efinance", "market_snapshot")) == "PASS":
        return "formula path can run from a full snapshot if efinance remains stable, but provider is not frozen and authorization still needs review."
    if by_capability.get(("baostock", "stock_universe")) == "PASS":
        return "universe and daily-history paths are available, but BaoStock lacks one-call latest snapshot; full-market breadth would need scheduled batch or another provider."
    return "not verified; no full-market or sufficient scheduled-batch capability was confirmed in this run."


def free_plan_conclusion(prior: dict[str, Any], provider_records: list[dict[str, Any]], valuation_records: list[dict[str, Any]]) -> str:
    has_financial = any(item.get("status") == "PASS" and str(item.get("capability", "")).startswith("financial_") for item in valuation_records)
    has_board = any(item.get("status") == "PASS" and item.get("capability") == "industry_boards" for item in provider_records)
    recommendation = prior.get("free_provider_recommendation", {}).get("answers", {}).get("1_free_plan_supports_personal_mvp")
    if has_financial and has_board:
        return f"partially sufficient for formulas and industry-board samples; still not enough to freeze provider. prior_free_spike={recommendation}"
    return f"not enough to freeze provider; financial, snapshot, concept, announcement or authorization gaps remain. prior_free_spike={recommendation}"


def build_provider_gaps(prior: dict[str, Any], provider_records: list[dict[str, Any]], valuation_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "gap": "latest full-market snapshot stability",
            "impact": "market breadth, limit-up/down and latest market overview",
            "degradation": "show last available daily batch, stale state, or no full-market breadth",
            "needs_second_source": "yes",
        },
        {
            "gap": "concept board and dynamic theme coverage",
            "impact": "hot concept boards and stock-to-board reverse mapping",
            "degradation": "industry boards only, concept board unavailable state, user-confirmed dynamic themes",
            "needs_second_source": "yes",
        },
        {
            "gap": "official announcements and event counts",
            "impact": "hot-stock event component and review material completeness",
            "degradation": "event_count unavailable or user-pasted official links only",
            "needs_second_source": "yes",
        },
        {
            "gap": "valuation financial fields and unit conventions",
            "impact": "PE/PB/PS/dividend valuation confidence and applicability",
            "degradation": "method unavailable with missing_data and not_applicable_reasons",
            "needs_second_source": "likely",
        },
        {
            "gap": "commercial authorization",
            "impact": "formal production launch and data redistribution",
            "degradation": "private validation only until legal/product review",
            "needs_second_source": "legal_review_required",
        },
    ]


def synthetic_probe(as_of_date: str | None) -> dict[str, Any]:
    return {
        "records": [
            {
                "provider": "synthetic",
                "capability": "network_probe",
                "api_name": "skip_network",
                "status": "SKIPPED",
                "row_count": 0,
                "fields_returned": [],
                "fallback": "Run without --skip-network to attempt provider probes.",
            }
        ],
        "valuation_records": [],
        "board_daily": synthetic_board_daily(),
        "market_breadth": {
            "input_scope": "synthetic_formula_sample",
            "as_of_date": as_of_date,
            "status": "SKIPPED",
            "missing_reasons": ["network probe skipped"],
        },
        "valuation_financials": synthetic_financials(),
    }


def synthetic_index_frame() -> pd.DataFrame:
    rows = []
    close = 1000.0
    start = pd.Timestamp("2026-04-01")
    for i in range(70):
        close *= 1.002
        rows.append({"trade_date": (start + pd.Timedelta(days=i)).date().isoformat(), "close": close})
    return pd.DataFrame(rows)


def synthetic_board_daily() -> dict[str, dict[str, pd.DataFrame]]:
    return {
        "standard_industry:semiconductor": {
            "688001.SH": make_daily("688001.SH", 20, 1.018),
            "688002.SH": make_daily("688002.SH", 18, 1.012),
            "300001.SZ": make_daily("300001.SZ", 12, 1.006),
        },
        "standard_industry:bank": {
            "000001.SZ": make_daily("000001.SZ", 12, 1.004),
            "600000.SH": make_daily("600000.SH", 10, 0.999),
            "601398.SH": make_daily("601398.SH", 6, 1.001),
        },
        "standard_industry:cyclical": {
            "600028.SH": make_daily("600028.SH", 8, 0.992),
            "601857.SH": make_daily("601857.SH", 9, 0.996),
            "600019.SH": make_daily("600019.SH", 7, 1.0),
        },
    }


def make_daily(symbol: str, base: float, daily_multiplier: float) -> pd.DataFrame:
    rows = []
    close = float(base)
    start = pd.Timestamp("2026-04-01")
    for i in range(70):
        pre = close
        close = close * daily_multiplier
        high = max(close, pre) * 1.01
        low = min(close, pre) * 0.99
        rows.append(
            {
                "symbol": symbol,
                "trade_date": (start + pd.Timedelta(days=i)).date().isoformat(),
                "open": pre,
                "high": high,
                "low": low,
                "close": close,
                "pre_close": pre,
                "pct_change": (close / pre - 1) * 100,
                "volume": 10_000_000 + i * 10_000,
                "amount": close * (10_000_000 + i * 10_000),
                "turnover_rate": 1 + i / 100,
                "trade_status": "trading",
                "is_st": False,
            }
        )
    return pd.DataFrame(rows)


def synthetic_event_counts(members: dict[str, pd.DataFrame]) -> dict[str, int]:
    return {symbol: index % 3 for index, symbol in enumerate(sorted(members), start=1)}


def synthetic_financials() -> list[dict[str, Any]]:
    records = [
        {
            "symbol": "600519.SH",
            "provider": "synthetic_formula_sample",
            "as_of_date": "2026-07-22",
            "report_period": "2025-12-31",
            "announcement_date": "2026-03-30",
            "fetched_at": "2026-07-22",
            "current_price": 1500,
            "total_shares": 1_256_000_000,
            "eps_ttm": 65,
            "revenue_ttm": 180_000_000_000,
            "net_profit_ttm": 82_000_000_000,
            "industry_pe_median": 22,
            "pe_bear": 18,
            "pe_base": 22,
            "pe_bull": 28,
            "dividend_per_share": 30,
            "dividend_history_years": 5,
        },
        {
            "symbol": "000001.SZ",
            "provider": "synthetic_formula_sample",
            "as_of_date": "2026-07-22",
            "report_period": "2025-12-31",
            "announcement_date": "2026-03-15",
            "fetched_at": "2026-07-22",
            "industry_type": "bank",
            "current_price": 12,
            "total_shares": 19_400_000_000,
            "bvps": 21,
            "roe": 11,
            "industry_pb_median": 0.65,
            "pb_bear": 0.5,
            "pb_base": 0.65,
            "pb_bull": 0.8,
            "eps_ttm": 1.8,
            "industry_pe_median": 7,
        },
        {
            "symbol": "300750.SZ",
            "provider": "synthetic_formula_sample",
            "as_of_date": "2026-07-22",
            "report_period": "2025-12-31",
            "announcement_date": "2026-04-20",
            "fetched_at": "2026-07-22",
            "current_price": 180,
            "total_shares": 4_400_000_000,
            "revenue_ttm": 380_000_000_000,
            "net_profit_ttm": -1_000_000_000,
            "revenue_growth": 25,
            "gross_margin": 22,
            "industry_ps_median": 2.4,
            "ps_bear": 1.8,
            "ps_base": 2.4,
            "ps_bull": 3.0,
        },
        {
            "symbol": "600028.SH",
            "provider": "synthetic_formula_sample",
            "as_of_date": "2026-07-22",
            "report_period": "2025-12-31",
            "announcement_date": "2026-03-25",
            "fetched_at": "2026-07-22",
            "industry_type": "cyclical",
            "current_price": 7,
            "total_shares": 121_000_000_000,
            "eps_ttm": 0.35,
            "normalized_eps": 0.55,
            "industry_pe_median": 10,
            "normalized_cycle_pe_bear": 6,
            "normalized_cycle_pe_base": 9,
            "normalized_cycle_pe_bull": 12,
            "dividend_per_share": 0.25,
            "dividend_history_years": 5,
        },
        {
            "symbol": "LOSS.SAMPLE",
            "provider": "synthetic_formula_sample",
            "as_of_date": "2026-07-22",
            "report_period": "2025-12-31",
            "announcement_date": "2026-04-25",
            "fetched_at": "2026-07-22",
            "current_price": 8,
            "total_shares": 1_000_000_000,
            "eps_ttm": -0.5,
            "net_profit_ttm": -500_000_000,
        },
    ]
    return [normalize_financial_record(record, as_of_date=record["as_of_date"]) for record in records]


if __name__ == "__main__":
    raise SystemExit(main())
