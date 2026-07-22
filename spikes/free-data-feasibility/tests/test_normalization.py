from __future__ import annotations

import pandas as pd

from src.normalization import (
    amount_to_yuan,
    empty_to_none,
    normalize_by_mapping,
    normalize_date,
    normalize_symbol,
    percent_value,
    provider_symbol,
    to_float,
    volume_to_shares,
)


def test_empty_values_are_not_zero() -> None:
    for value in ["", "--", "-", "None", "NaN", None, float("nan")]:
        assert empty_to_none(value) is None
        assert to_float(value) is None


def test_units_are_normalized() -> None:
    assert volume_to_shares(12, "hand") == 1200
    assert volume_to_shares("2", "10k_share") == 20000
    assert amount_to_yuan(3, "10k_yuan") == 30000
    assert amount_to_yuan(4, "100m_yuan") == 400000000
    assert percent_value("4.82%") == 4.82


def test_symbol_and_date_normalization() -> None:
    assert normalize_symbol("600519") == "600519.SH"
    assert normalize_symbol("000001") == "000001.SZ"
    assert normalize_symbol("1") == "000001.SZ"
    assert normalize_symbol("300750") == "300750.SZ"
    assert normalize_symbol("688981") == "688981.SH"
    assert normalize_symbol("bj.830799") == "830799.BJ"
    assert provider_symbol("600519.SH", "baostock") == "sh.600519"
    assert provider_symbol("000001.SZ", "akshare") == "000001"
    assert normalize_date("20260722") == "2026-07-22"


def test_chinese_field_mapping_keeps_missing_as_none() -> None:
    frame = pd.DataFrame(
        [
            {
                "代码": "600519",
                "日期": "2026-07-22",
                "开盘": "100",
                "收盘": "--",
                "成交量": "10",
                "成交额": "2000",
                "涨跌幅": "1.23",
            }
        ]
    )
    normalized = normalize_by_mapping(
        frame,
        mapping={"symbol": "代码", "trade_date": "日期", "open": "开盘", "close": "收盘", "volume": "成交量", "amount": "成交额", "pct_change": "涨跌幅"},
        provider="akshare",
        volume_unit="hand",
        amount_unit="yuan",
    )

    row = normalized.iloc[0]
    assert row["symbol"] == "600519.SH"
    assert row["trade_date"] == "2026-07-22"
    assert row["volume"] == 1000
    assert row["amount"] == 2000
    assert row["close"] is None
