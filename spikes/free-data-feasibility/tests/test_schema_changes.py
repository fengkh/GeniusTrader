from __future__ import annotations

import pandas as pd

from src.providers.akshare_provider import AKShareProvider


class ChangedAKModule:
    __version__ = "changed"

    @staticmethod
    def stock_zh_a_spot_em() -> pd.DataFrame:
        return pd.DataFrame({"unexpected": [1]})


def test_schema_change_is_recorded_with_returned_fields() -> None:
    provider = AKShareProvider(module=ChangedAKModule(), request_interval=0)

    result = provider.get_stock_snapshot(["600519"])

    assert result.record.status == "SCHEMA_MISMATCH"
    assert result.record.fields_returned == ["unexpected"]
    assert "required raw columns missing" in (result.record.error_message or "")
