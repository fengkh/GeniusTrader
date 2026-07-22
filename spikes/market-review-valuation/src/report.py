from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def write_reports(
    *,
    output_dir: Path,
    manifest: dict[str, Any],
    provider_records: list[dict[str, Any]],
    market_review: dict[str, Any],
    board_rankings: list[dict[str, Any]],
    stock_rankings_by_board: dict[str, list[dict[str, Any]]],
    watch_candidates: dict[str, Any],
    valuation_records: list[dict[str, Any]],
    valuations: list[dict[str, Any]],
    provider_gaps: list[dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    write_json(output_dir / "run_manifest.json", manifest)
    write_json(output_dir / "market_review.json", market_review)
    write_json(output_dir / "valuations.json", {"valuations": valuations, "provider_records": valuation_records})

    (output_dir / "market_capability_report.md").write_text(market_capability_report(provider_records, market_review), encoding="utf-8")
    (output_dir / "market_review_report.md").write_text(market_review_report(market_review, watch_candidates), encoding="utf-8")
    (output_dir / "board_ranking_report.md").write_text(board_ranking_report(board_rankings), encoding="utf-8")
    (output_dir / "stock_ranking_report.md").write_text(stock_ranking_report(stock_rankings_by_board), encoding="utf-8")
    (output_dir / "valuation_capability_report.md").write_text(valuation_capability_report(valuation_records, valuations), encoding="utf-8")
    (output_dir / "valuation_report.md").write_text(valuation_report(valuations), encoding="utf-8")
    (output_dir / "provider_gap_report.md").write_text(provider_gap_report(provider_gaps), encoding="utf-8")
    assert_no_secret(output_dir)


def _status_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(item.get("status", "UNKNOWN")) for item in records))


def market_capability_report(records: list[dict[str, Any]], market_review: dict[str, Any]) -> str:
    lines = [
        "# Market Capability Report",
        "",
        "This spike validates feasibility only. It does not select a final data provider.",
        "",
        f"- Network completed: {market_review.get('network_completed')}",
        f"- Probe scope: {market_review.get('input_scope')}",
        f"- Status counts: {json.dumps(_status_counts(records), ensure_ascii=False)}",
        "",
        "## Required Answers",
        "",
        f"- Whole-market review implementable: {market_review.get('whole_market_review_conclusion')}",
        f"- Hot boards calculable: {market_review.get('hot_boards_conclusion')}",
        f"- Board continuity calculable: {market_review.get('board_continuity_conclusion')}",
        f"- Hot stocks within boards calculable: {market_review.get('hot_stocks_conclusion')}",
        f"- Observation candidates can form: {market_review.get('watch_candidates_conclusion')}",
        f"- Free plan enough: {market_review.get('free_plan_conclusion')}",
        "",
        "| provider | capability | api | status | rows | latest | fallback | error |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- |",
    ]
    for record in records:
        lines.append(
            f"| {record.get('provider')} | {record.get('capability')} | {record.get('api_name')} | {record.get('status')} | {record.get('row_count')} | {record.get('latest_date') or ''} | {record.get('fallback') or ''} | {record.get('error_message') or ''} |"
        )
    return "\n".join(lines) + "\n"


def market_review_report(market_review: dict[str, Any], watch_candidates: dict[str, Any]) -> str:
    breadth = market_review.get("market_breadth", {})
    lines = [
        "# Market Review Report",
        "",
        "All values are program-calculated from the probe input. Limited samples are not treated as a full-market conclusion.",
        "",
        f"- Data scope: {market_review.get('input_scope')}",
        f"- As of date: {breadth.get('as_of_date')}",
        f"- Up/down/flat/suspended: {breadth.get('up_count')}/{breadth.get('down_count')}/{breadth.get('flat_count')}/{breadth.get('suspended_count')}",
        f"- Limit up/down: {breadth.get('limit_up_count')}/{breadth.get('limit_down_count')}",
        f"- Total amount: {breadth.get('total_amount')}",
        f"- 20d new high/low count: {breadth.get('new_high_20d_count')}/{breadth.get('new_low_20d_count')}",
        f"- Above MA20 ratio: {breadth.get('above_ma20_ratio')}",
        "",
        "## Next-Day Observation Candidates",
        "",
        f"- Board candidates: {len(watch_candidates.get('boards', []))}",
        f"- Stock candidates: {len(watch_candidates.get('stocks', []))}",
        "- Boundary: observation candidates are not trading instructions, position advice or return promises.",
    ]
    return "\n".join(lines) + "\n"


def board_ranking_report(board_rankings: list[dict[str, Any]]) -> str:
    lines = [
        "# Board Ranking Report",
        "",
        "Board heat is decomposed into raw and standardized components. The total score is not an opaque AI label.",
        "",
        "| rank | board | type | stage | score | completeness | missing |",
        "| ---: | --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in board_rankings:
        lines.append(
            f"| {row.get('rank')} | {row.get('board_name')} | {row.get('board_type')} | {row.get('board_stage')} | {row.get('heat_score')} | {row.get('data_completeness')} | {', '.join(row.get('missing_components', []))} |"
        )
    return "\n".join(lines) + "\n"


def stock_ranking_report(stock_rankings_by_board: dict[str, list[dict[str, Any]]]) -> str:
    lines = [
        "# Stock Ranking Report",
        "",
        "Roles such as leader/core/follow are system suggestions with rules and confidence, not investment recommendations.",
        "",
        "| board | rank | symbol | score | role | completeness | penalties |",
        "| --- | ---: | --- | ---: | --- | ---: | --- |",
    ]
    for board_id, rows in stock_rankings_by_board.items():
        for row in rows:
            penalties = ",".join(item["type"] for item in row.get("risk_penalties", []))
            role = (row.get("role_suggestion") or {}).get("role")
            lines.append(f"| {board_id} | {row.get('rank_in_board')} | {row.get('symbol')} | {row.get('score')} | {role} | {row.get('data_completeness')} | {penalties} |")
    return "\n".join(lines) + "\n"


def valuation_capability_report(records: list[dict[str, Any]], valuations: list[dict[str, Any]]) -> str:
    status_counts = _status_counts(records)
    unavailable = [item for item in valuations if item.get("confidence_level") == "unavailable"]
    lines = [
        "# Valuation Capability Report",
        "",
        "Valuation outputs are model estimates. They are not factual values, price targets, trading advice or return guarantees.",
        "",
        f"- Financial probe status counts: {json.dumps(status_counts, ensure_ascii=False)}",
        f"- Valuation samples: {len(valuations)}",
        f"- Unavailable valuation count: {len(unavailable)}",
        "",
        "## Method Feasibility",
        "",
        "- PE: feasible when positive EPS TTM and usable valuation multiples exist.",
        "- PB-ROE: feasible for banks/insurance/net-asset-driven companies when BVPS and ROE exist.",
        "- PS: feasible when revenue TTM and share count exist; useful when profit is unstable.",
        "- Dividend yield: feasible when stable dividend data and yield assumptions exist.",
        "- Normalized cycle: feasible when cyclical normalized EPS or cycle-average EPS exists.",
        "- DCF: only data-sufficiency feasibility in V1 spike; no formal DCF valuation interval is produced.",
    ]
    return "\n".join(lines) + "\n"


def valuation_report(valuations: list[dict[str, Any]]) -> str:
    lines = [
        "# Valuation Report",
        "",
        "Valuation intervals are model estimates with explicit assumptions and data gaps.",
        "",
        "| symbol | methods | price | low | base | high | confidence | missing | not applicable |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- | --- |",
    ]
    for row in valuations:
        lines.append(
            f"| {row.get('symbol')} | {', '.join(row.get('selected_methods', []))} | {row.get('current_price')} | {row.get('fair_value_low')} | {row.get('fair_value_base')} | {row.get('fair_value_high')} | {row.get('confidence_level')} | {', '.join(row.get('missing_data', []))} | {', '.join(row.get('not_applicable_reasons', []))} |"
        )
    return "\n".join(lines) + "\n"


def provider_gap_report(gaps: list[dict[str, Any]]) -> str:
    lines = [
        "# Provider Gap Report",
        "",
        "Provider gaps remain open product or technical questions. No supplier is selected by this spike.",
        "",
        "| gap | impact | degradation | needs paid or second source |",
        "| --- | --- | --- | --- |",
    ]
    for gap in gaps:
        lines.append(f"| {gap['gap']} | {gap['impact']} | {gap['degradation']} | {gap['needs_second_source']} |")
    return "\n".join(lines) + "\n"


def assert_no_secret(output_dir: Path) -> None:
    secret_words = ["api_key=", "token=", "password=", "cookie=", "secret="]
    for path in output_dir.glob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore").lower()
        for word in secret_words:
            if word in text:
                raise RuntimeError(f"secret-like value found in {path.name}")
