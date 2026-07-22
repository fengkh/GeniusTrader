from __future__ import annotations

import pytest

from src.financial_normalization import FutureDataError, normalize_financial_record


@pytest.mark.parametrize(
    "field,value",
    [
        ("report_period", "2026-09-30"),
        ("announcement_date", "2026-09-30"),
        ("fetched_at", "2026-09-30"),
    ],
)
def test_future_financial_dates_are_rejected(field: str, value: str) -> None:
    record = {
        "symbol": "600001.SH",
        "report_period": "2026-03-31",
        "announcement_date": "2026-04-30",
        "fetched_at": "2026-05-01",
        field: value,
    }

    with pytest.raises(FutureDataError):
        normalize_financial_record(record, as_of_date="2026-07-22")
