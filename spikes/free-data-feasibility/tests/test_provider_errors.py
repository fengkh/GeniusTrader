from __future__ import annotations

import pandas as pd

from src.capability import classify_exception
from src.providers.base import BaseProvider


class FakeModule:
    __version__ = "fake"

    @staticmethod
    def ok() -> pd.DataFrame:
        return pd.DataFrame({"x": [1]})

    @staticmethod
    def empty() -> pd.DataFrame:
        return pd.DataFrame()

    @staticmethod
    def network() -> pd.DataFrame:
        raise TimeoutError("network timeout")


class FakeProvider(BaseProvider):
    provider_name = "fake"

    def _import_module(self) -> FakeModule:
        return FakeModule()


def test_exception_statuses_are_normalized() -> None:
    assert classify_exception(TimeoutError("network timeout")) == "NETWORK_ERROR"
    assert classify_exception(RuntimeError("too many requests rate limit")) == "RATE_LIMITED"
    assert classify_exception(ValueError("invalid parameter")) == "INVALID_REQUEST"
    assert classify_exception(AttributeError("has no attribute foo")) == "SOURCE_CHANGED"


def test_empty_and_unsupported_are_distinct() -> None:
    provider = FakeProvider(module=FakeModule())
    empty = provider._call(capability="empty", api_name="empty", parameters={}, fields_expected=[], impacts=[], fallback="")
    missing = provider._call(capability="missing", api_name="missing", parameters={}, fields_expected=[], impacts=[], fallback="")

    assert empty.record.status == "PASS_EMPTY"
    assert missing.record.status == "SOURCE_CHANGED"


def test_network_error_is_not_swallowed() -> None:
    provider = FakeProvider(module=FakeModule(), request_interval=0)
    result = provider._call(capability="network", api_name="network", parameters={}, fields_expected=[], impacts=[], fallback="")

    assert result.record.status == "NETWORK_ERROR"
    assert "timeout" in (result.record.error_message or "")
