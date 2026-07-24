from __future__ import annotations

from ..metrics.coverage import completeness_summary, missing_field_counts


def render(records: list[dict], results: list[dict]) -> str:
    lines = [
        "# Announcement Feasibility Report",
        "",
        f"- Announcement samples: {len(records)}",
        f"- Completeness: `{completeness_summary(records)}`",
        f"- Missing fields: `{missing_field_counts(records)}`",
        "",
        "## Provider Results",
        "",
        "| Provider | Status | Samples | Evidence |",
        "| --- | --- | ---: | --- |",
    ]
    for result in results:
        if "announcement" not in result["capability"]:
            continue
        evidence = "; ".join(result.get("evidence", [])[:2])
        lines.append(f"| {result['provider']} | {result['status']} | {result.get('sample_count', 0)} | {evidence} |")
    lines += [
        "",
        "## Findings",
        "",
        "- Provider IDs, publication time, title, source page, and PDF/document URL are the core fields to freeze before production.",
        "- Stock relation should prefer explicit provider symbols; missing symbols must remain unmatched.",
        "- Corrections and multi-security announcements need separate production rules.",
    ]
    return "\n".join(lines) + "\n"
