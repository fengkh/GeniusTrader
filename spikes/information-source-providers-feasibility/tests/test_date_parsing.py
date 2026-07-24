from src.date_utils import effective_date, parse_datetime


def test_parse_china_datetime_and_epoch_ms():
    assert effective_date(parse_datetime("2026-07-24 09:30:00")) == "2026-07-24"
    assert parse_datetime(1_721_788_800_000) is not None


def test_parse_invalid_datetime_returns_none():
    assert parse_datetime("not-a-date") is None
