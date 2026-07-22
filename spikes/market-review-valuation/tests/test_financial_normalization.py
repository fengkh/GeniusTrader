from __future__ import annotations

from src.financial_normalization import normalize_financial_record, select_financials_as_of


def test_financial_normalization_derives_ratios_and_keeps_missing_none() -> None:
    result = normalize_financial_record(
        {
            "symbol": "600001.SH",
            "provider": "unit-test",
            "report_period": "2026-03-31",
            "announcement_date": "2026-04-30",
            "fetched_at": "2026-07-22",
            "current_price": "10",
            "total_shares": "100000000",
            "net_profit_ttm": "500000000",
            "net_assets": "2000000000",
            "revenue_ttm": "3000000000",
        },
        as_of_date="2026-07-22",
    )

    assert result["eps_ttm"] == 5.0
    assert result["bvps"] == 20.0
    assert result["pe_ttm"] == 2.0
    assert result["pb"] == 0.5
    assert result["ps_ttm"] is not None
    assert "free_cash_flow" in result["missing_data"]


def test_select_financials_as_of_ignores_future_records() -> None:
    selected = select_financials_as_of(
        [
            {"symbol": "600001.SH", "report_period": "2026-03-31", "announcement_date": "2026-04-30", "fetched_at": "2026-05-01", "current_price": 10},
            {"symbol": "600001.SH", "report_period": "2026-09-30", "announcement_date": "2026-10-30", "fetched_at": "2026-10-31", "current_price": 11},
        ],
        as_of_date="2026-07-22",
    )

    assert selected is not None
    assert selected["report_period"] == "2026-03-31"
