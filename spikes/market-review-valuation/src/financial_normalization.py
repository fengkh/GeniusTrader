from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pandas as pd

FORMULA_VERSION = "gt-financial-normalization-v0.1"


class FutureDataError(ValueError):
    """Raised when a financial record is later than the valuation as-of date."""


def parse_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    try:
        return pd.to_datetime(value).date()
    except Exception:  # noqa: BLE001
        return None


def parse_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        parsed = pd.to_numeric(value, errors="coerce")
    except Exception:  # noqa: BLE001
        return None
    if pd.isna(parsed):
        return None
    return float(parsed)


def _require_not_future(record_date: date | None, as_of: date, field: str) -> None:
    if record_date and record_date > as_of:
        raise FutureDataError(f"{field} {record_date.isoformat()} is later than as_of_date {as_of.isoformat()}")


def normalize_financial_record(record: dict[str, Any], *, as_of_date: str | date) -> dict[str, Any]:
    as_of = parse_date(as_of_date)
    if as_of is None:
        raise ValueError("as_of_date is required")
    report_period = parse_date(record.get("report_period") or record.get("statDate") or record.get("end_date"))
    announcement_date = parse_date(record.get("announcement_date") or record.get("pubDate") or record.get("ann_date"))
    fetched_at = parse_date(record.get("fetched_at")) or date.today()
    _require_not_future(report_period, as_of, "report_period")
    _require_not_future(announcement_date, as_of, "announcement_date")
    _require_not_future(fetched_at, as_of, "fetched_at")

    normalized: dict[str, Any] = {
        "symbol": record.get("symbol") or record.get("code") or record.get("ts_code"),
        "as_of_date": as_of.isoformat(),
        "report_period": None if report_period is None else report_period.isoformat(),
        "announcement_date": None if announcement_date is None else announcement_date.isoformat(),
        "fetched_at": fetched_at.isoformat(),
        "provider": record.get("provider"),
        "industry_type": record.get("industry_type") or record.get("industry"),
        "formula_version": FORMULA_VERSION,
    }
    numeric_fields = [
        "current_price",
        "total_shares",
        "float_shares",
        "current_market_value",
        "freefloat_market_value",
        "eps_ttm",
        "net_profit_ttm",
        "revenue_ttm",
        "revenue",
        "net_assets",
        "bvps",
        "roe",
        "gross_margin",
        "net_margin",
        "operating_cash_flow",
        "free_cash_flow",
        "debt_ratio",
        "interest_bearing_debt",
        "cash_equivalents",
        "dividend_per_share",
        "dividend_history_years",
        "normalized_eps",
        "cycle_average_eps",
        "cycle_average_profit",
        "historical_pe_percentile",
        "historical_pb_percentile",
        "historical_ps_percentile",
        "industry_pe_median",
        "industry_pb_median",
        "industry_ps_median",
        "industry_roe_median",
        "revenue_growth",
        "pe_ttm",
        "pb",
        "ps_ttm",
        "pe_bear",
        "pe_base",
        "pe_bull",
        "pb_bear",
        "pb_base",
        "pb_bull",
        "ps_bear",
        "ps_base",
        "ps_bull",
        "dividend_yield_bear",
        "dividend_yield_base",
        "dividend_yield_bull",
        "normalized_cycle_pe_bear",
        "normalized_cycle_pe_base",
        "normalized_cycle_pe_bull",
    ]
    for field in numeric_fields:
        normalized[field] = parse_number(record.get(field))

    if normalized["current_market_value"] is None and normalized["current_price"] is not None and normalized["total_shares"] is not None:
        normalized["current_market_value"] = normalized["current_price"] * normalized["total_shares"]
    if normalized["freefloat_market_value"] is None and normalized["current_price"] is not None and normalized["float_shares"] is not None:
        normalized["freefloat_market_value"] = normalized["current_price"] * normalized["float_shares"]
    if normalized["eps_ttm"] is None and normalized["net_profit_ttm"] is not None and normalized["total_shares"]:
        normalized["eps_ttm"] = normalized["net_profit_ttm"] / normalized["total_shares"]
    if normalized["cycle_average_eps"] is None and normalized["cycle_average_profit"] is not None and normalized["total_shares"]:
        normalized["cycle_average_eps"] = normalized["cycle_average_profit"] / normalized["total_shares"]
    if normalized["bvps"] is None and normalized["net_assets"] is not None and normalized["total_shares"]:
        normalized["bvps"] = normalized["net_assets"] / normalized["total_shares"]
    if normalized["pe_ttm"] is None and normalized["current_price"] is not None and normalized["eps_ttm"] and normalized["eps_ttm"] > 0:
        normalized["pe_ttm"] = normalized["current_price"] / normalized["eps_ttm"]
    if normalized["pb"] is None and normalized["current_price"] is not None and normalized["bvps"] and normalized["bvps"] > 0:
        normalized["pb"] = normalized["current_price"] / normalized["bvps"]
    if normalized["ps_ttm"] is None and normalized["current_market_value"] is not None and normalized["revenue_ttm"] and normalized["revenue_ttm"] > 0:
        normalized["ps_ttm"] = normalized["current_market_value"] / normalized["revenue_ttm"]

    required = [
        "current_price",
        "current_market_value",
        "eps_ttm",
        "revenue_ttm",
        "bvps",
        "roe",
        "gross_margin",
        "operating_cash_flow",
        "free_cash_flow",
        "dividend_per_share",
    ]
    missing = [field for field in required if normalized.get(field) is None]
    normalized["missing_data"] = missing
    normalized["data_completeness"] = round((len(required) - len(missing)) / len(required) * 100, 4)
    normalized["input_sources"] = list(record.get("input_sources") or ([record.get("provider")] if record.get("provider") else []))
    return normalized


def select_financials_as_of(records: list[dict[str, Any]], *, as_of_date: str | date) -> dict[str, Any] | None:
    as_of = parse_date(as_of_date)
    if as_of is None:
        raise ValueError("as_of_date is required")
    valid: list[dict[str, Any]] = []
    for record in records:
        try:
            normalized = normalize_financial_record(record, as_of_date=as_of)
        except FutureDataError:
            continue
        valid.append(normalized)
    if not valid:
        return None
    valid.sort(key=lambda item: (item.get("announcement_date") or "", item.get("report_period") or ""))
    return valid[-1]
