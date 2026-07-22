from __future__ import annotations

from typing import Any

FORMULA_VERSION = "gt-valuation-v0.1"


def _value(financial: dict[str, Any], field: str) -> float | None:
    value = financial.get(field)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _implied(fair_value: float | None, current_price: float | None) -> float | None:
    if fair_value is None or current_price is None or current_price <= 0:
        return None
    return (fair_value / current_price - 1) * 100


def _confidence(financial: dict[str, Any], required: list[str], *, method: str) -> tuple[str, list[str]]:
    missing = [field for field in required if financial.get(field) is None]
    if missing:
        return "low", [f"missing: {', '.join(missing)}"]
    completeness = _value(financial, "data_completeness") or 0
    if completeness >= 80:
        return "high", [f"{method} inputs complete and data_completeness >= 80"]
    if completeness >= 60:
        return "medium", [f"{method} inputs complete but broader financial data has gaps"]
    return "low", [f"{method} core inputs available but financial completeness is low"]


def unavailable_result(financial: dict[str, Any], method: str, reasons: list[str], missing: list[str] | None = None) -> dict[str, Any]:
    return {
        "symbol": financial.get("symbol"),
        "as_of_date": financial.get("as_of_date"),
        "financial_period": financial.get("report_period"),
        "current_price": financial.get("current_price"),
        "current_market_value": financial.get("current_market_value"),
        "selected_methods": [method],
        "fair_value_low": None,
        "fair_value_base": None,
        "fair_value_high": None,
        "implied_return_low": None,
        "implied_return_base": None,
        "implied_return_high": None,
        "confidence_level": "unavailable",
        "confidence_reasons": ["valuation unavailable because required data or method conditions are missing"],
        "assumptions": [],
        "missing_data": missing or financial.get("missing_data", []),
        "not_applicable_reasons": reasons,
        "formula_version": FORMULA_VERSION,
        "input_sources": financial.get("input_sources", []),
        "boundary": "Valuation interval is a model estimate, not factual value, trading advice or a return promise.",
    }


def valuation_result(financial: dict[str, Any], method: str, low: float, base: float, high: float, assumptions: list[str], confidence: str, confidence_reasons: list[str]) -> dict[str, Any]:
    current_price = _value(financial, "current_price")
    low, high = min(low, base, high), max(low, base, high)
    return {
        "symbol": financial.get("symbol"),
        "as_of_date": financial.get("as_of_date"),
        "financial_period": financial.get("report_period"),
        "current_price": current_price,
        "current_market_value": financial.get("current_market_value"),
        "selected_methods": [method],
        "fair_value_low": round(low, 4),
        "fair_value_base": round(base, 4),
        "fair_value_high": round(high, 4),
        "implied_return_low": None if _implied(low, current_price) is None else round(_implied(low, current_price), 4),
        "implied_return_base": None if _implied(base, current_price) is None else round(_implied(base, current_price), 4),
        "implied_return_high": None if _implied(high, current_price) is None else round(_implied(high, current_price), 4),
        "confidence_level": confidence,
        "confidence_reasons": confidence_reasons,
        "assumptions": assumptions,
        "missing_data": financial.get("missing_data", []),
        "not_applicable_reasons": [],
        "formula_version": FORMULA_VERSION,
        "input_sources": financial.get("input_sources", []),
        "boundary": "Valuation interval is a model estimate, not factual value, trading advice or a return promise.",
    }


def pe_valuation(financial: dict[str, Any]) -> dict[str, Any]:
    eps = _value(financial, "eps_ttm")
    current_price = _value(financial, "current_price")
    if current_price is None:
        return unavailable_result(financial, "stable_pe", ["current_price_required"], ["current_price"])
    if eps is None or eps <= 0:
        return unavailable_result(financial, "stable_pe", ["positive_stable_profit_required"], ["eps_ttm"])
    base = _value(financial, "pe_base") or _value(financial, "industry_pe_median")
    if base is None or base <= 0:
        return unavailable_result(financial, "stable_pe", ["valuation_multiple_required"], ["industry_pe_median or pe_base"])
    bear = _value(financial, "pe_bear") or max(base * 0.75, 4.0)
    bull = _value(financial, "pe_bull") or max(base * 1.2, bear * 1.4)
    confidence, reasons = _confidence(financial, ["current_price", "eps_ttm", "industry_pe_median"], method="PE")
    assumptions = [
        f"bear/base/bull PE multiples: {bear:.2f}/{base:.2f}/{bull:.2f}",
        "PE range applies only when positive earnings are not abnormal.",
    ]
    return valuation_result(financial, "stable_pe", eps * bear, eps * base, eps * bull, assumptions, confidence, reasons)


def pb_roe_valuation(financial: dict[str, Any]) -> dict[str, Any]:
    bvps = _value(financial, "bvps")
    roe = _value(financial, "roe")
    if bvps is None or bvps <= 0:
        return unavailable_result(financial, "pb_roe", ["positive_bvps_required"], ["bvps"])
    if roe is None:
        return unavailable_result(financial, "pb_roe", ["roe_required"], ["roe"])
    base = _value(financial, "pb_base") or _value(financial, "industry_pb_median")
    if base is None or base <= 0:
        return unavailable_result(financial, "pb_roe", ["valuation_multiple_required"], ["industry_pb_median or pb_base"])
    bear = _value(financial, "pb_bear") or max(base * 0.75, 0.2)
    bull = _value(financial, "pb_bull") or base * 1.25
    confidence, reasons = _confidence(financial, ["current_price", "bvps", "roe", "industry_pb_median"], method="PB-ROE")
    assumptions = [
        f"bear/base/bull PB multiples: {bear:.2f}/{base:.2f}/{bull:.2f}",
        f"current ROE input: {roe:.2f}",
    ]
    return valuation_result(financial, "pb_roe", bvps * bear, bvps * base, bvps * bull, assumptions, confidence, reasons)


def ps_valuation(financial: dict[str, Any]) -> dict[str, Any]:
    revenue_ttm = _value(financial, "revenue_ttm")
    shares = _value(financial, "total_shares")
    if revenue_ttm is None or revenue_ttm <= 0:
        return unavailable_result(financial, "ps_growth", ["positive_revenue_required"], ["revenue_ttm"])
    if shares is None or shares <= 0:
        return unavailable_result(financial, "ps_growth", ["total_shares_required"], ["total_shares"])
    revenue_per_share = revenue_ttm / shares
    base = _value(financial, "ps_base") or _value(financial, "industry_ps_median")
    if base is None or base <= 0:
        return unavailable_result(financial, "ps_growth", ["valuation_multiple_required"], ["industry_ps_median or ps_base"])
    bear = _value(financial, "ps_bear") or max(base * 0.7, 0.2)
    bull = _value(financial, "ps_bull") or base * 1.35
    confidence, reasons = _confidence(financial, ["current_price", "revenue_ttm", "total_shares", "industry_ps_median"], method="PS")
    assumptions = [
        f"bear/base/bull PS multiples: {bear:.2f}/{base:.2f}/{bull:.2f}",
        "PS range is used for revenue-driven companies where earnings may be unstable.",
    ]
    return valuation_result(financial, "ps_growth", revenue_per_share * bear, revenue_per_share * base, revenue_per_share * bull, assumptions, confidence, reasons)


def dividend_valuation(financial: dict[str, Any]) -> dict[str, Any]:
    dps = _value(financial, "dividend_per_share")
    if dps is None or dps <= 0:
        return unavailable_result(financial, "dividend_yield", ["positive_dividend_required"], ["dividend_per_share"])
    bear_yield = (_value(financial, "dividend_yield_bear") or 5.0) / 100
    base_yield = (_value(financial, "dividend_yield_base") or 4.0) / 100
    bull_yield = (_value(financial, "dividend_yield_bull") or 3.2) / 100
    yields = [bear_yield, base_yield, bull_yield]
    if any(item <= 0 for item in yields):
        return unavailable_result(financial, "dividend_yield", ["positive_yield_assumptions_required"], ["dividend_yield assumptions"])
    low = dps / max(yields)
    base = dps / base_yield
    high = dps / min(yields)
    confidence, reasons = _confidence(financial, ["current_price", "dividend_per_share", "dividend_history_years"], method="Dividend")
    assumptions = [
        f"bear/base/bull dividend yields: {max(yields) * 100:.2f}%/{base_yield * 100:.2f}%/{min(yields) * 100:.2f}%",
        "Dividend valuation requires sustainability review; trading volume does not raise intrinsic value.",
    ]
    return valuation_result(financial, "dividend_yield", low, base, high, assumptions, confidence, reasons)


def normalized_cycle_valuation(financial: dict[str, Any]) -> dict[str, Any]:
    normalized_eps = _value(financial, "normalized_eps") or _value(financial, "cycle_average_eps")
    current_price = _value(financial, "current_price")
    if current_price is None:
        return unavailable_result(financial, "normalized_cycle", ["current_price_required"], ["current_price"])
    if normalized_eps is None or normalized_eps <= 0:
        return unavailable_result(financial, "normalized_cycle", ["positive_normalized_cycle_eps_required"], ["normalized_eps"])
    base = _value(financial, "normalized_cycle_pe_base") or _value(financial, "industry_pe_median")
    if base is None or base <= 0:
        return unavailable_result(financial, "normalized_cycle", ["valuation_multiple_required"], ["industry_pe_median or normalized_cycle_pe_base"])
    bear = _value(financial, "normalized_cycle_pe_bear") or max(base * 0.65, 4.0)
    bull = _value(financial, "normalized_cycle_pe_bull") or base * 1.35
    confidence, reasons = _confidence(financial, ["current_price", "normalized_eps", "industry_pe_median"], method="Normalized cycle")
    if _value(financial, "normalized_eps") is None and _value(financial, "cycle_average_eps") is not None:
        reasons.append("cycle_average_eps used as normalized EPS proxy")
    assumptions = [
        f"bear/base/bull normalized-cycle PE multiples: {bear:.2f}/{base:.2f}/{bull:.2f}",
        "Normalized-cycle valuation is for cyclical companies and depends on explicit normalized earnings input.",
    ]
    return valuation_result(financial, "normalized_cycle", normalized_eps * bear, normalized_eps * base, normalized_eps * bull, assumptions, confidence, reasons)


def dcf_feasibility(financial: dict[str, Any]) -> dict[str, Any]:
    required = [
        "revenue_growth",
        "net_margin",
        "free_cash_flow",
        "interest_bearing_debt",
        "cash_equivalents",
        "total_shares",
    ]
    missing = [field for field in required if financial.get(field) is None]
    result = unavailable_result(financial, "dcf_feasibility", ["dcf_not_formal_v1_valuation"], missing)
    result["selected_methods"] = ["dcf_feasibility"]
    result["confidence_level"] = "unavailable" if missing else "low"
    result["confidence_reasons"] = [
        "DCF feasibility only checks data sufficiency in this spike; it does not output a formal V1 valuation interval."
    ]
    result["assumptions"] = [
        "revenue growth, margin, free cash flow, debt, cash and share count must come from disclosed data or user-confirmed assumptions.",
    ]
    return result
