from __future__ import annotations

from ..metrics.capability import capability_matrix, success_rate
from ..metrics.performance import latency_summary
from ..metrics.stability import stability_summary


def render(results: list[dict]) -> str:
    matrix = capability_matrix(results)
    lines = [
        "# Provider Capability Report",
        "",
        "This is a feasibility spike report, not a production provider decision.",
        "",
        f"- Result count: {len(results)}",
        f"- PASS/PARTIAL rate: {success_rate(results):.2%}",
        f"- Stability: `{stability_summary(results)}`",
        f"- Latency: `{latency_summary(results)}`",
        "",
        "## Capability Matrix",
        "",
        "| Provider | Capabilities |",
        "| --- | --- |",
    ]
    for provider, capabilities in sorted(matrix.items()):
        summary = ", ".join(f"{capability}: {status}" for capability, status in sorted(capabilities.items()))
        lines.append(f"| {provider} | {summary} |")
    lines += ["", "## Limitations", "", "- Public accessibility is not authorization for commercial use or redistribution.", "- Manual legal and business review is required before production."]
    return "\n".join(lines) + "\n"
