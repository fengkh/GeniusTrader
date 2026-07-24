from __future__ import annotations

from ..metrics.coverage import completeness_summary, missing_field_counts


def render(records: list[dict], results: list[dict]) -> str:
    lines = [
        "# News Feasibility Report",
        "",
        f"- News samples: {len(records)}",
        f"- Completeness: `{completeness_summary(records)}`",
        f"- Missing fields: `{missing_field_counts(records)}`",
        "",
        "## Provider Results",
        "",
        "| Provider | Capability | Status | Samples |",
        "| --- | --- | --- | ---: |",
    ]
    for result in results:
        if "news" in result["capability"] or "rss" in result["capability"]:
            lines.append(f"| {result['provider']} | {result['capability']} | {result['status']} | {result.get('sample_count', 0)} |")
    lines += [
        "",
        "## Findings",
        "",
        "- Public pages can be useful for manual URL intake and source discovery.",
        "- Automatic news collection has higher copyright and redistribution uncertainty than official announcement metadata.",
        "- Full-text storage and summary generation rights remain open questions.",
    ]
    return "\n".join(lines) + "\n"
