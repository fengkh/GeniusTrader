from __future__ import annotations

from src.valuation_models import pb_roe_valuation


def test_pb_roe_valuation_for_net_asset_driven_company() -> None:
    result = pb_roe_valuation(
        {
            "symbol": "000001.SZ",
            "current_price": 12,
            "bvps": 20,
            "roe": 10,
            "industry_pb_median": 0.7,
            "data_completeness": 85,
        }
    )

    assert result["selected_methods"] == ["pb_roe"]
    assert result["fair_value_base"] == 14
    assert result["confidence_level"] == "high"
