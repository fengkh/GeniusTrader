from __future__ import annotations

from src.valuation_models import ps_valuation


def test_ps_valuation_for_revenue_driven_company() -> None:
    result = ps_valuation(
        {
            "symbol": "300001.SZ",
            "current_price": 18,
            "revenue_ttm": 1_000_000_000,
            "total_shares": 100_000_000,
            "industry_ps_median": 2.0,
            "data_completeness": 70,
        }
    )

    assert result["selected_methods"] == ["ps_growth"]
    assert result["fair_value_base"] == 20
    assert result["confidence_level"] == "medium"
