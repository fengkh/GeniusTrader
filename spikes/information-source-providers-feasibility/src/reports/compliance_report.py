from __future__ import annotations


def render(results: list[dict]) -> str:
    lines = [
        "# Compliance And Authorization Report",
        "",
        "This is not legal advice. It records public technical observations only.",
        "",
        "| Provider | Preliminary Status | Notes |",
        "| --- | --- | --- |",
    ]
    for result in results:
        notes = "; ".join(result.get("limitations", [])[:2]) or "manual review required"
        status = "public_but_terms_unclear"
        if result["status"] in {"ACCESS_DENIED", "AUTH_REQUIRED"}:
            status = "authorization_required"
        elif result["status"] in {"RATE_LIMITED"}:
            status = "automated_access_restricted"
        lines.append(f"| {result['provider']} | {status} | {notes} |")
    lines += [
        "",
        "## Open Items",
        "",
        "- Terms of service and robots.txt do not equal complete authorization.",
        "- Production launch requires legal and commercial authorization review.",
        "- Full-text storage and redistribution need separate approval.",
    ]
    return "\n".join(lines) + "\n"
