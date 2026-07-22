from __future__ import annotations

from src.valuation_models import pe_valuation


def test_pe_valuation_requires_positive_profit_and_outputs_interval() -> None:
    result = pe_valuation(
        {
            "symbol": "600001.SH",
            "as_of_date": "2026-07-22",
            "report_period": "2026-03-31",
            "current_price": 20,
            "eps_ttm": 2,
            "industry_pe_median": 12,
            "data_completeness": 90,
        }
    )

    assert result["selected_methods"] == ["stable_pe"]
    assert result["fair_value_low"] <= result["fair_value_base"] <= result["fair_value_high"]
    assert result["confidence_level"] == "high"
    assert "trading advice" in result["boundary"]


def test_pe_valuation_unavailable_for_negative_eps() -> None:
    result = pe_valuation({"symbol": "LOSS", "current_price": 8, "eps_ttm": -0.5})

    assert result["confidence_level"] == "unavailable"
    assert "positive_stable_profit_required" in result["not_applicable_reasons"]


def test_pe_valuation_does_not_use_current_price_as_benchmark() -> None:
    result = pe_valuation({"symbol": "NO_BENCHMARK", "current_price": 20, "eps_ttm": 2, "pe_ttm": 10})

    assert result["confidence_level"] == "unavailable"
    assert "valuation_multiple_required" in result["not_applicable_reasons"]
