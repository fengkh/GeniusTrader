from __future__ import annotations

import pandas as pd

from src.capability import normalize_exception, redact_text
from src.tushare_provider import TushareProvider, latest_ended_trade_date, select_bse_symbol


class EmptyClient:
    def query(self, api_name: str, fields: str = "", **kwargs: object) -> pd.DataFrame:
        return pd.DataFrame()


class PermissionClient:
    def query(self, api_name: str, fields: str = "", **kwargs: object) -> pd.DataFrame:
        raise RuntimeError("抱歉，您没有访问该接口的权限，token=SECRET_TOKEN_VALUE_1234567890")


def test_error_status_normalization() -> None:
    assert normalize_exception(RuntimeError("积分不足"))[0] == "PERMISSION_DENIED"
    assert normalize_exception(RuntimeError("访问频率超过限制"))[0] == "RATE_LIMITED"
    assert normalize_exception(RuntimeError("invalid field"))[0] == "INVALID_REQUEST"
    assert normalize_exception(RuntimeError("network timeout"))[0] == "API_ERROR"


def test_redact_text_hides_token() -> None:
    text = redact_text("token=SECRET_TOKEN_VALUE_1234567890", "SECRET_TOKEN_VALUE_1234567890")

    assert text is not None
    assert "SECRET_TOKEN_VALUE_1234567890" not in text
    assert "[REDACTED" in text


def test_empty_data_is_pass_empty_not_permission_error() -> None:
    provider = TushareProvider("test-token", pro_client=EmptyClient())

    frame, record = provider.query(capability="empty probe", api_name="daily")

    assert frame.empty
    assert record.status == "PASS_EMPTY"


def test_permission_error_is_distinct_from_empty_data() -> None:
    provider = TushareProvider("SECRET_TOKEN_VALUE_1234567890", pro_client=PermissionClient())

    frame, record = provider.query(capability="permission probe", api_name="anns_d")

    assert frame.empty
    assert record.status == "PERMISSION_DENIED"
    assert "SECRET_TOKEN_VALUE_1234567890" not in (record.permission_or_error_message or "")


def test_latest_ended_trade_date_does_not_assume_natural_day() -> None:
    cal = pd.DataFrame(
        {
            "cal_date": ["20260720", "20260721", "20260722"],
            "is_open": [1, 1, 1],
        }
    )
    now = pd.Timestamp("2026-07-22T10:00:00+08:00").to_pydatetime()

    assert latest_ended_trade_date(cal, now) == "20260721"


def test_bse_selection_is_deterministic() -> None:
    stock_basic = pd.DataFrame(
        {
            "ts_code": ["920002.BJ", "920001.BJ", "000001.SZ"],
            "exchange": ["BSE", "BSE", "SZSE"],
            "list_status": ["L", "L", "L"],
        }
    )

    symbol, reason = select_bse_symbol(stock_basic)

    assert reason is None
    assert symbol == "920001.BJ"
