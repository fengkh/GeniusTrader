from __future__ import annotations

from src.valuation_models import dividend_valuation


def test_dividend_valuation_outputs_yield_based_interval() -> None:
    result = dividend_valuation(
        {
            "symbol": "600001.SH",
            "current_price": 10,
            "dividend_per_share": 0.5,
            "dividend_history_years": 5,
            "data_completeness": 80,
        }
    )

    assert result["selected_methods"] == ["dividend_yield"]
    assert result["fair_value_low"] == 10
    assert result["fair_value_base"] == 12.5
    assert result["fair_value_high"] == 15.625
    assert result["confidence_level"] == "high"
