from pathlib import Path


def test_announcement_sync_limit_copy_uses_provider_limits_not_hardcoded_values():
    repo_root = Path(__file__).resolve().parents[2]
    page_source = (repo_root / "src/app/information/announcements/page.tsx").read_text(encoding="utf-8")

    assert "\u6700\u591a 20 \u53ea\u80a1\u7968" not in page_source
    assert "\u6700\u591a 50 \u6761\u8bb0\u5f55" not in page_source
    assert "currentProvider.limits.max_symbols_per_run" in page_source
    assert "currentProvider.limits.max_records_per_run" in page_source


def test_review_detail_regenerate_button_uses_backend_running_state():
    repo_root = Path(__file__).resolve().parents[2]
    page_source = (repo_root / "src/app/reviews/[reviewId]/page.tsx").read_text(encoding="utf-8")
    types_source = (repo_root / "src/lib/api/types.ts").read_text(encoding="utf-8")

    assert "generation_in_progress: boolean" in types_source
    assert "review?.generation_in_progress" in page_source
    assert "const actionDisabled = workingAction !== null || generationInProgress" in page_source
    assert "disabled={actionDisabled}" in page_source
    assert "setWorkingAction(\"regenerate\")" in page_source
    assert "生成中" in page_source
