from __future__ import annotations

import pandas as pd
import pytest

from src.market_breadth import compute_market_breadth

from conftest import make_daily


def test_market_breadth_counts_and_no_empty_zero_confusion() -> None:
    snapshot = pd.DataFrame(
        [
            {"symbol": "600001.SH", "market": "SH", "close": 11, "pre_close": 10, "high": 11.2, "low": 9.9, "amount": 100, "trade_status": "trading", "total_market_value": 1000, "style": "value"},
            {"symbol": "000001.SZ", "market": "SZ", "close": 9.5, "pre_close": 10, "high": 10, "low": 9.4, "amount": 80, "trade_status": "trading", "total_market_value": 900, "style": "value"},
            {"symbol": "300001.SZ", "market": "SZ", "close": 10, "pre_close": 10, "high": 10.1, "low": 9.9, "amount": 60, "trade_status": "trading", "total_market_value": 500, "style": "growth"},
            {"symbol": "688001.SH", "market": "SH", "close": None, "pre_close": None, "amount": None, "trade_status": "suspended", "total_market_value": 700, "style": "growth"},
        ]
    )
    history = {
        "600001.SH": make_daily("600001.SH", start_close=8, multiplier=1.01),
        "000001.SZ": make_daily("000001.SZ", start_close=12, multiplier=0.99),
        "300001.SZ": make_daily("300001.SZ", start_close=10, multiplier=1.0),
    }
    result = compute_market_breadth(snapshot, history_by_symbol=history, previous_total_amount=200, as_of_date="2026-07-22")

    assert result["status"] == "PASS"
    assert result["up_count"] == 1
    assert result["down_count"] == 1
    assert result["flat_count"] == 1
    assert result["suspended_count"] == 1
    assert result["limit_up_count"] == 1
    assert result["amount_change_pct"] == pytest.approx(20.0)
    assert result["new_high_20d_count"] is not None


def test_empty_market_breadth_uses_unknown_counts() -> None:
    result = compute_market_breadth(None, as_of_date="2026-07-22")

    assert result["status"] == "PASS_EMPTY"
    assert result["stock_count"] == 0
    assert result["up_count"] is None
    assert result["total_amount"] is None
