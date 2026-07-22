from __future__ import annotations

import importlib

import pytest

from src.market_breadth import compute_market_breadth
from src.market_universe import probe_baostock_market_data


def test_missing_baostock_dependency_returns_upstream_error(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = importlib.import_module

    def fake_import(name: str, package: str | None = None):
        if name == "baostock":
            raise ModuleNotFoundError("baostock missing")
        return original_import(name, package)

    monkeypatch.setattr(importlib, "import_module", fake_import)

    result = probe_baostock_market_data(max_boards=1, max_stocks_per_board=1, days=10, request_interval=0)

    assert result["network_completed"] is False
    assert result["records"][0]["status"] == "UPSTREAM_ERROR"
    assert result["market_breadth"]["status"] == "PASS_EMPTY"


def test_empty_snapshot_does_not_report_fake_zero_counts() -> None:
    result = compute_market_breadth([], as_of_date="2026-07-22")

    assert result["stock_count"] == 0
    assert result["up_count"] is None
    assert result["down_count"] is None
