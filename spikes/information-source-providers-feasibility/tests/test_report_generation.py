from src.reports.capability_report import render as render_capability


def test_report_generation_no_cookie_or_token():
    text = render_capability(
        [
            {
                "provider": "cninfo",
                "capability": "announcement_list",
                "status": "PASS",
                "request_count": 1,
                "success_count": 1,
                "failure_count": 0,
                "latency_ms": 1,
                "sample_count": 1,
                "evidence": ["https://example.com"],
                "limitations": [],
            }
        ]
    )
    assert "Cookie" not in text
    assert "Token" not in text
    assert "cninfo" in text
