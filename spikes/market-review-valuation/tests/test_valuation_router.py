from __future__ import annotations

from src.valuation_router import route_valuation, select_methods


def test_router_selects_pb_first_for_financial_companies() -> None:
    financial = {
        "symbol": "000001.SZ",
        "industry_type": "bank",
        "current_price": 12,
        "bvps": 20,
        "roe": 10,
        "industry_pb_median": 0.7,
        "eps_ttm": 1.5,
        "industry_pe_median": 8,
        "data_completeness": 90,
    }

    result = route_valuation(financial)

    assert select_methods(financial)[:2] == ["pb_roe", "stable_pe"]
    assert result["selected_methods"][:2] == ["pb_roe", "stable_pe"]
    assert result["fair_value_base"] == 14
    assert "AI may explain assumptions" in result["router_boundary"]


def test_router_marks_insufficient_data_unavailable() -> None:
    result = route_valuation({"symbol": "UNKNOWN"})

    assert result["selected_methods"] == ["insufficient_data"]
    assert result["confidence_level"] == "unavailable"


def test_router_supports_normalized_cycle_method() -> None:
    financial = {
        "symbol": "600028.SH",
        "industry_type": "cyclical",
        "current_price": 7,
        "normalized_eps": 0.5,
        "industry_pe_median": 10,
        "data_completeness": 80,
    }

    result = route_valuation(financial)

    assert result["selected_methods"][0] == "normalized_cycle"
    assert result["fair_value_base"] == 5
    assert result["confidence_level"] == "high"
