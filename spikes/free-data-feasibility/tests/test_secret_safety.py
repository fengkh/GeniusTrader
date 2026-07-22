from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from src.capability import synthetic_record
from src.models import RunManifest
from src.report import assert_no_secret, write_reports


def test_report_writer_does_not_emit_secret_parameters(tmp_path: Path) -> None:
    record = synthetic_record(
        provider="akshare",
        provider_version="test",
        capability="secret_probe",
        api_name="fake",
        status="UPSTREAM_ERROR",
        parameters_summary={"api_key": "SECRET_TOKEN_VALUE_1234567890"},
        error_message="api_key=SECRET_TOKEN_VALUE_1234567890 failed",
    )
    manifest = RunManifest(
        generated_at="2026-07-22T12:00:00+08:00",
        timezone="Asia/Shanghai",
        python_version="3.12",
        providers_requested=["akshare"],
        symbols_requested=["000001.SZ"],
        days=220,
        percentile_window=120,
        request_interval=1.0,
        stability_runs=1,
        skipped={"minute": True, "boards": True, "announcements": True},
        package_versions={"akshare": "test"},
        api_signatures={"akshare": {"fake": "()"}},
        documentation_sources=[],
    )

    write_reports(
        output_dir=tmp_path,
        manifest=manifest,
        capability_records=[record],
        stability_results=[],
        comparison_results=[],
        metric_results=[],
        quality_issues=[],
        sample_summary=pd.DataFrame([{"provider": "akshare"}]),
    )

    for path in tmp_path.glob("*"):
        assert "SECRET_TOKEN_VALUE_1234567890" not in path.read_text(encoding="utf-8", errors="ignore")


def test_secret_detector_fails_on_cookie_like_text(tmp_path: Path) -> None:
    (tmp_path / "bad.txt").write_text("cookie=abc", encoding="utf-8")

    with pytest.raises(RuntimeError):
        assert_no_secret(tmp_path)
