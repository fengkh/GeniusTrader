from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.models import CapabilityRecord, MetricResult, QualityIssue, SpikeContext
from src.report import write_reports


def test_token_does_not_appear_in_reports(tmp_path: Path) -> None:
    token = "SECRET_TOKEN_VALUE_1234567890"
    context = SpikeContext(
        provider="tushare",
        queried_at="2026-07-22T12:00:00+08:00",
        shanghai_now="2026-07-22T12:00:00+08:00",
        latest_trade_date="20260721",
        days=180,
        percentile_window=120,
        symbols=["000001.SZ"],
        skipped_optional=False,
    )
    records = [
        CapabilityRecord(
            capability="permission probe",
            api_name="anns_d",
            status="PERMISSION_DENIED",
            queried_at=context.queried_at,
            parameters_summary={"token": "[REDACTED_TOKEN]"},
            fields_requested=[],
            fields_returned=[],
            row_count=0,
            earliest_date=None,
            latest_date=None,
            duration_ms=1,
            unit_notes="",
            permission_or_error_message="permission denied [REDACTED_TOKEN]",
            impacts_features=["announcements"],
            recommended_fallback="manual link",
        )
    ]
    metrics = [
        MetricResult(
            symbol="000001.SZ",
            metric="5d_return",
            value=1.0,
            unit="percent",
            formula_version="test",
            input_data_source="mock",
            window="5d",
            as_of_date="20260721",
            status="PASS",
        )
    ]
    quality = [
        QualityIssue(
            symbol="000001.SZ",
            dataset="daily",
            check_name="date_duplicates",
            status="PASS",
            message="ok",
        )
    ]

    write_reports(
        output_dir=tmp_path,
        context=context,
        capability_records=records,
        metric_results=metrics,
        quality_issues=quality,
        sample_summary=pd.DataFrame([{"ts_code": "000001.SZ"}]),
        token=token,
    )

    for path in tmp_path.glob("*"):
        assert token not in path.read_text(encoding="utf-8", errors="ignore")


def test_report_writer_detects_token_leak(tmp_path: Path) -> None:
    token = "SECRET_TOKEN_VALUE_1234567890"
    (tmp_path / "leak.txt").write_text(token, encoding="utf-8")

    from src.report import assert_no_token

    with pytest.raises(RuntimeError):
        assert_no_token(tmp_path, token)
