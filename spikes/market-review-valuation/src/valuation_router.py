from __future__ import annotations

from typing import Any

from .valuation_models import dcf_feasibility, dividend_valuation, normalized_cycle_valuation, pb_roe_valuation, pe_valuation, ps_valuation, unavailable_result

FORMULA_VERSION = "gt-valuation-router-v0.1"


def select_methods(financial: dict[str, Any]) -> list[str]:
    methods: list[str] = []
    industry_type = str(financial.get("industry_type") or "").lower()
    eps = financial.get("eps_ttm")
    revenue = financial.get("revenue_ttm")
    bvps = financial.get("bvps")
    roe = financial.get("roe")
    dividend = financial.get("dividend_per_share")
    normalized_eps = financial.get("normalized_eps") or financial.get("cycle_average_eps")
    if industry_type in {"cyclical", "cycle", "materials", "steel", "coal", "energy", "chemical"}:
        methods.append("normalized_cycle")
    if industry_type in {"bank", "banks", "insurance", "financial"} and bvps is not None and roe is not None:
        methods.append("pb_roe")
    if eps is not None and eps > 0 and financial.get("profit_abnormal") is not True:
        methods.append("stable_pe")
    if revenue is not None and revenue > 0 and (eps is None or eps <= 0 or (financial.get("revenue_growth") or 0) >= 20):
        methods.append("ps_growth")
    if dividend is not None and dividend > 0 and (financial.get("dividend_history_years") or 0) >= 3:
        methods.append("dividend_yield")
    if normalized_eps is not None and "normalized_cycle" not in methods:
        methods.append("normalized_cycle")
    dcf_fields = ["revenue_growth", "net_margin", "free_cash_flow", "interest_bearing_debt", "cash_equivalents", "total_shares"]
    if any(financial.get(field) is not None for field in dcf_fields):
        methods.append("dcf_feasibility")
    return _dedupe(methods) or ["insufficient_data"]


def route_valuation(financial: dict[str, Any]) -> dict[str, Any]:
    selected = select_methods(financial)
    method_results = []
    for method in selected:
        if method == "stable_pe":
            method_results.append(pe_valuation(financial))
        elif method == "pb_roe":
            method_results.append(pb_roe_valuation(financial))
        elif method == "ps_growth":
            method_results.append(ps_valuation(financial))
        elif method == "dividend_yield":
            method_results.append(dividend_valuation(financial))
        elif method == "normalized_cycle":
            method_results.append(normalized_cycle_valuation(financial))
        elif method == "dcf_feasibility":
            method_results.append(dcf_feasibility(financial))
        else:
            method_results.append(unavailable_result(financial, "insufficient_data", ["insufficient_data"], financial.get("missing_data", [])))
    primary = next((item for item in method_results if item.get("confidence_level") != "unavailable" and item.get("fair_value_base") is not None), method_results[0])
    combined = dict(primary)
    combined["selected_methods"] = selected
    combined["method_results"] = method_results
    combined["formula_version"] = FORMULA_VERSION
    combined["router_boundary"] = "Program selects valuation methods. AI may explain assumptions and gaps but cannot choose methods or invent numbers."
    return combined


def _dedupe(items: list[str]) -> list[str]:
    seen = set()
    result = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result
