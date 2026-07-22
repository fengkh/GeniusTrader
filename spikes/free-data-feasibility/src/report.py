from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from .capability import redact_text
from .models import CapabilityRecord, ComparisonFieldResult, MetricResult, QualityIssue, RunManifest, StabilityRunResult


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def capability_summary(records: list[CapabilityRecord]) -> dict[str, Any]:
    counts = Counter(record.status for record in records)
    by_provider: dict[str, Counter[str]] = defaultdict(Counter)
    critical = [
        "stock_universe",
        "stock_snapshot",
        "daily_history",
        "daily_history_qfq",
        "index_history",
        "minute_history",
        "industry_boards",
        "concept_boards",
        "stock_status",
        "announcements",
    ]
    for record in records:
        by_provider[record.provider][record.status] += 1
    critical_rows = [
        record.to_dict()
        for record in records
        if record.capability in critical or any(key in record.capability for key in critical)
    ]
    return {
        "status_counts": dict(counts),
        "by_provider": {provider: dict(counter) for provider, counter in by_provider.items()},
        "critical_records": critical_rows,
        "unsupported": [record.to_dict() for record in records if record.status in {"NOT_SUPPORTED", "SOURCE_CHANGED"}],
    }


def stability_summary(results: list[StabilityRunResult]) -> dict[str, Any]:
    grouped: dict[str, list[StabilityRunResult]] = defaultdict(list)
    for result in results:
        grouped[f"{result.provider}:{result.capability}"].append(result)
    rows = []
    for key, items in grouped.items():
        fields_sets = {tuple(item.fields_returned) for item in items}
        row_counts = {item.row_count for item in items}
        latest_dates = {item.latest_date for item in items}
        status_counts = Counter(item.status for item in items)
        success_ratio = status_counts.get("PASS", 0) / len(items) if items else 0
        rows.append(
            {
                "key": key,
                "runs": len(items),
                "status_counts": dict(status_counts),
                "fields_stable": len(fields_sets) <= 1,
                "row_count_stable": len(row_counts) <= 1,
                "latest_date_stable": len(latest_dates) <= 1,
                "average_duration_ms": sum(item.duration_ms for item in items) / len(items) if items else None,
                "stability_score_0_100": round(success_ratio * 60 + (20 if len(fields_sets) <= 1 else 0) + (10 if len(row_counts) <= 1 else 0) + (10 if len(latest_dates) <= 1 else 0), 2),
            }
        )
    return {"items": rows}


def metrics_summary(results: list[MetricResult]) -> dict[str, Any]:
    counts = Counter(result.status for result in results)
    by_provider = defaultdict(Counter)
    by_metric = defaultdict(Counter)
    for result in results:
        by_provider[result.provider][result.status] += 1
        by_metric[result.metric][result.status] += 1
    return {
        "status_counts": dict(counts),
        "by_provider": {provider: dict(counter) for provider, counter in by_provider.items()},
        "by_metric": {metric: dict(counter) for metric, counter in by_metric.items()},
        "success_count": counts.get("PASS", 0),
        "total_count": len(results),
    }


def comparison_summary(results: list[ComparisonFieldResult]) -> dict[str, Any]:
    compared = [result for result in results if result.compared_rows > 0]
    mismatches = [result for result in compared if result.mismatch_rows > 0]
    return {
        "field_result_count": len(results),
        "comparable_field_result_count": len(compared),
        "mismatch_field_result_count": len(mismatches),
        "mismatches": [result.to_dict() for result in mismatches[:50]],
    }


def quality_summary(issues: list[QualityIssue]) -> dict[str, Any]:
    counts = Counter(issue.status for issue in issues)
    return {
        "status_counts": dict(counts),
        "issues": [issue.to_dict() for issue in issues if issue.status != "PASS"],
    }


def capability_markdown(records: list[CapabilityRecord]) -> str:
    lines = [
        "# Free Data Provider Capability Report",
        "",
        "This isolated spike validates AKShare, efinance and BaoStock as candidate free-provider components. It does not select a final provider.",
        "",
        "## Summary",
        "",
        json.dumps(capability_summary(records)["status_counts"], ensure_ascii=False),
        "",
        "| provider | capability | api | status | rows | earliest | latest | source | fallback | error |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- | --- | --- |",
    ]
    for record in records:
        lines.append(
            "| "
            + " | ".join(
                [
                    record.provider,
                    record.capability,
                    record.api_name,
                    record.status,
                    str(record.row_count),
                    record.earliest_date or "",
                    record.latest_date or "",
                    record.source_type,
                    record.recommended_fallback,
                    record.error_message or "",
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def stability_markdown(results: list[StabilityRunResult]) -> str:
    lines = [
        "# Stability Report",
        "",
        "Scores are rough spike diagnostics only; they are not reliability promises.",
        "",
        "| provider | capability | run | status | rows | latest | duration_ms | error |",
        "| --- | --- | ---: | --- | ---: | --- | ---: | --- |",
    ]
    for result in results:
        lines.append(
            f"| {result.provider} | {result.capability} | {result.run_index} | {result.status} | {result.row_count} | {result.latest_date or ''} | {result.duration_ms} | {result.error_message or ''} |"
        )
    return "\n".join(lines) + "\n"


def comparison_markdown(results: list[ComparisonFieldResult]) -> str:
    lines = [
        "# Cross Provider Comparison Report",
        "",
        "Only common unadjusted daily trade dates are compared. Adjusted-price comparisons should focus on returns, not absolute prices.",
        "",
        "| symbol | provider_a | provider_b | field | rows | exact | within_tolerance | mismatch | max_abs | max_rel | reason |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for result in results:
        lines.append(
            f"| {result.symbol} | {result.provider_a} | {result.provider_b} | {result.field} | {result.compared_rows} | {result.exact_match_rows} | {result.within_tolerance_rows} | {result.mismatch_rows} | {_fmt_number(result.max_absolute_difference)} | {_fmt_number(result.max_relative_difference)} | {result.likely_reason} |"
        )
    return "\n".join(lines) + "\n"


def _fmt_number(value: float | None) -> str:
    return "" if value is None else f"{value:.6g}"


def metrics_markdown(results: list[MetricResult]) -> str:
    lines = [
        "# Metrics Report",
        "",
        "Metrics are program-calculated from each provider's own normalized data. AI must not generate or backfill these values.",
        "",
        f"- Summary: {json.dumps(metrics_summary(results)['status_counts'], ensure_ascii=False)}",
        "",
        "| provider | symbol | metric | status | value | unit | window | as_of_date | missing_reason |",
        "| --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
    ]
    for result in results:
        value = "" if result.value is None else f"{result.value:.6f}"
        lines.append(
            f"| {result.provider} | {result.symbol} | {result.metric} | {result.status} | {value} | {result.unit} | {result.window} | {result.as_of_date or ''} | {result.missing_reason or ''} |"
        )
    return "\n".join(lines) + "\n"


def quality_markdown(issues: list[QualityIssue]) -> str:
    lines = [
        "# Data Quality Report",
        "",
        f"- Summary: {json.dumps(quality_summary(issues)['status_counts'], ensure_ascii=False)}",
        "",
        "| provider | symbol | dataset | check | status | message | affected_dates |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for issue in issues:
        lines.append(
            f"| {issue.provider} | {issue.symbol} | {issue.dataset} | {issue.check_name} | {issue.status} | {issue.message} | {', '.join(issue.affected_dates)} |"
        )
    return "\n".join(lines) + "\n"


def provider_recommendation(capabilities: list[CapabilityRecord], metrics: list[MetricResult], comparisons: list[ComparisonFieldResult]) -> dict[str, Any]:
    by_provider = defaultdict(list)
    for record in capabilities:
        by_provider[record.provider].append(record)
    metric_counts = metrics_summary(metrics)["by_provider"]
    comparison = comparison_summary(comparisons)

    daily_rank = _rank_providers(by_provider, "daily_history")
    snapshot_rank = _rank_providers(by_provider, "stock_snapshot")
    history_rank = _rank_providers(by_provider, "daily_history")
    industry_rank = _rank_providers(by_provider, "industry_boards")
    concept_rank = _rank_providers(by_provider, "concept_boards")
    main_daily = daily_rank[0]["provider"] if daily_rank and daily_rank[0]["pass_count"] > 0 else "not_verified"
    latest_main = snapshot_rank[0]["provider"] if snapshot_rank and snapshot_rank[0]["pass_count"] > 0 else "not_verified"
    fallback_history = "baostock" if any(item["provider"] == "baostock" and item["pass_count"] > 0 for item in history_rank) else main_daily
    latest_snapshot_stable = bool(snapshot_rank and snapshot_rank[0]["pass_count"] >= snapshot_rank[0]["failure_count"] and snapshot_rank[0]["pass_count"] > 0)
    daily_stable = bool(daily_rank and daily_rank[0]["pass_count"] >= daily_rank[0]["failure_count"] and daily_rank[0]["pass_count"] > 0)
    enough = daily_stable and latest_snapshot_stable and len(metric_counts) > 0
    return {
        "answers": {
            "1_free_plan_supports_personal_mvp": "conditionally_yes_after_product_owner_review" if enough else "not_enough_to_freeze_provider; adapter_design_can_continue",
            "2_daily_k_stable": _status_sentence(by_provider, "daily_history"),
            "3_latest_snapshot_stable": _status_sentence(by_provider, "stock_snapshot"),
            "4_minute_available": _status_sentence(by_provider, "minute_history"),
            "5_bse_coverage": _status_sentence(by_provider, "stock_universe"),
            "6_industry_and_concept_available": _status_sentence(by_provider, "boards"),
            "7_stock_to_board_reverse_mapping": "Build by cached board-member mapping when public reverse lookup is unavailable; spike caps sample scans at 10 boards.",
            "8_metric_success_count": metrics_summary(metrics),
            "9_metrics_to_degrade": [metric for metric, counter in metrics_summary(metrics)["by_metric"].items() if counter.get("PASS", 0) == 0],
            "10_recommended_main_provider": main_daily,
            "11_recommended_backup_provider": "efinance" if main_daily != "efinance" and any(item["provider"] == "efinance" and item["pass_count"] > 0 for item in daily_rank) else "akshare_if_network_recovers",
            "12_recommended_historical_floor_provider": fallback_history,
            "13_auto_switch_strategy": "Route by capability: snapshot and boards prefer AKShare if stable, daily fallback to efinance then BaoStock; never merge providers inside one metric.",
            "14_enter_formal_backend_development": "yes_for_adapter_design_only; no_provider_freeze_until_snapshot_and_authorization_are_verified" if main_daily != "not_verified" else "no_until_daily_and_snapshot_are_verified",
            "15_need_second_batch_provider_validation": "yes, especially for announcements/legal authorization and production-grade quote licensing.",
            "16_largest_technical_risk": "Public upstream schema/rate-limit changes can break free libraries without notice.",
            "17_largest_data_semantics_risk": "Volume, amount, turnover, adjustment and board membership definitions may differ across providers.",
            "18_commercial_authorization_risk": "LEGAL_REVIEW_REQUIRED; library license does not grant market-data commercial rights.",
        },
        "routes": {
            "stock_basic_provider": "akshare_if_universe_passes_else_manual_or_paid_source",
            "latest_snapshot_main_provider": latest_main,
            "latest_snapshot_backup_provider": "not_verified",
            "daily_main_provider": main_daily,
            "daily_backup_provider": "efinance" if main_daily != "efinance" and any(item["provider"] == "efinance" and item["pass_count"] > 0 for item in daily_rank) else "akshare_if_network_recovers",
            "historical_floor_provider": fallback_history,
            "minute_provider": "akshare_or_efinance_if_minute_history_passes",
            "index_provider": "akshare_if_index_history_passes_else_baostock",
            "industry_board_provider": industry_rank[0]["provider"] if industry_rank and industry_rank[0]["pass_count"] > 0 else "not_verified",
            "concept_board_provider": concept_rank[0]["provider"] if concept_rank and concept_rank[0]["pass_count"] > 0 else "not_verified",
            "announcement_provider": "not_verified",
            "stock_status_provider": "provider_snapshot_or_daily_status_if_passes",
        },
        "ranking_notes": {
            "daily_rank": daily_rank,
            "snapshot_rank": snapshot_rank,
            "industry_rank": industry_rank,
            "concept_rank": concept_rank,
        },
        "comparison_summary": comparison,
    }


def write_reports(
    *,
    output_dir: Path,
    manifest: RunManifest,
    capability_records: list[CapabilityRecord],
    stability_results: list[StabilityRunResult],
    comparison_results: list[ComparisonFieldResult],
    metric_results: list[MetricResult],
    quality_issues: list[QualityIssue],
    sample_summary: pd.DataFrame,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    recommendation = provider_recommendation(capability_records, metric_results, comparison_results)

    write_json(output_dir / "run_manifest.json", manifest.to_dict())
    write_json(output_dir / "capability_report.json", {"summary": capability_summary(capability_records), "records": [record.to_dict() for record in capability_records]})
    write_json(output_dir / "stability_report.json", {"summary": stability_summary(stability_results), "runs": [result.to_dict() for result in stability_results]})
    write_json(output_dir / "comparison_report.json", {"summary": comparison_summary(comparison_results), "results": [result.to_dict() for result in comparison_results]})
    write_json(output_dir / "metrics_report.json", {"summary": metrics_summary(metric_results), "metrics": [result.to_dict() for result in metric_results]})
    write_json(output_dir / "provider_recommendation.json", recommendation)
    write_json(output_dir / "data_quality_report.json", {"summary": quality_summary(quality_issues), "checks": [issue.to_dict() for issue in quality_issues]})

    (output_dir / "capability_report.md").write_text(capability_markdown(capability_records), encoding="utf-8")
    (output_dir / "stability_report.md").write_text(stability_markdown(stability_results), encoding="utf-8")
    (output_dir / "comparison_report.md").write_text(comparison_markdown(comparison_results), encoding="utf-8")
    (output_dir / "metrics_report.md").write_text(metrics_markdown(metric_results), encoding="utf-8")
    (output_dir / "provider_recommendation.md").write_text(recommendation_markdown(recommendation), encoding="utf-8")
    (output_dir / "data_quality_report.md").write_text(quality_markdown(quality_issues), encoding="utf-8")
    sample_summary.to_csv(output_dir / "sample_summary.csv", index=False, encoding="utf-8")
    assert_no_secret(output_dir)


def recommendation_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Provider Recommendation",
        "",
        "This is a spike recommendation, not a final supplier decision.",
        "",
        "## Required Questions",
        "",
    ]
    for key, value in payload["answers"].items():
        lines.append(f"- {key}: {json.dumps(value, ensure_ascii=False)}")
    lines.extend(["", "## Candidate Routes", ""])
    for key, value in payload["routes"].items():
        lines.append(f"- {key}: {value}")
    return "\n".join(lines) + "\n"


def assert_no_secret(output_dir: Path) -> None:
    assignment_pattern = re.compile(r"(?i)(token|api_key|apikey|password|secret|cookie)=([^\s&\"'}\]]+)")
    for path in output_dir.glob("*"):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if assignment_pattern.search(text):
            raise RuntimeError(f"Secret-like value found in report {path.name}")
        if "SECRET_TOKEN_VALUE" in text:
            raise RuntimeError(f"Secret-like value found in report {path.name}")
        redacted = redact_text(text) or ""
        lowered = redacted.lower()
        if "secret_token_value" in lowered:
            raise RuntimeError(f"Secret-like value found in report {path.name}")


def _status_sentence(by_provider: dict[str, list[CapabilityRecord]], capability_keyword: str) -> str:
    statuses = {}
    for provider, records in by_provider.items():
        matches = [record.status for record in records if capability_keyword in record.capability]
        if matches:
            statuses[provider] = Counter(matches).most_common(1)[0][0]
    return json.dumps(statuses or {"not_verified": "no records"}, ensure_ascii=False)


def _rank_providers(by_provider: dict[str, list[CapabilityRecord]], capability_keyword: str) -> list[dict[str, Any]]:
    ranked = []
    failure_statuses = {"NETWORK_ERROR", "UPSTREAM_ERROR", "RATE_LIMITED", "SOURCE_CHANGED", "SCHEMA_MISMATCH", "UNIT_UNCERTAIN", "INVALID_REQUEST"}
    for provider, records in by_provider.items():
        matches = [record for record in records if capability_keyword in record.capability]
        if not matches:
            continue
        pass_count = sum(1 for record in matches if record.status in {"PASS", "PARTIAL_PASS"})
        failure_count = sum(1 for record in matches if record.status in failure_statuses)
        rows = sum(record.row_count for record in matches if record.status in {"PASS", "PARTIAL_PASS"})
        ranked.append({"provider": provider, "pass_count": pass_count, "failure_count": failure_count, "row_count": rows, "score": pass_count * 3 - failure_count})
    return sorted(ranked, key=lambda item: (item["score"], item["pass_count"], item["row_count"]), reverse=True)
