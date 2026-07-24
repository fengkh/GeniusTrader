from __future__ import annotations


def _status(results: list[dict], provider: str, capability: str) -> str:
    for result in results:
        if result["provider"] == provider and result["capability"] == capability:
            return result["status"]
    return "NOT_TESTED"


def render(results: list[dict]) -> str:
    cninfo = _status(results, "cninfo", "announcement_list")
    sse = _status(results, "sse", "announcement_list")
    szse = _status(results, "szse", "announcement_list")
    bse = _status(results, "bse", "announcement_list")
    has_technical_candidate = cninfo in {"PASS", "PARTIAL"} and (sse in {"PASS", "PARTIAL"} or szse in {"PASS", "PARTIAL"})
    lines = [
        "# Provider Recommendation",
        "",
        f"- Announcement technical candidate: {'CNINFO' if cninfo in {'PASS', 'PARTIAL'} else 'No stable candidate from this run'}",
        f"- Announcement backup candidates: SSE={sse}, SZSE={szse}, BSE={bse}",
        "- News primary candidate: No production freeze from this spike; prefer user-submitted URL plus official pages until authorization is clarified.",
        "- News backup candidate: Public regulator/exchange pages for manual URL intake and future authorization review.",
        "- Manual URL only: ordinary public news pages, company official news pages, pages without stable incremental APIs.",
        "- Not recommended: login pages, comment areas, paid content, CAPTCHA-protected pages, or sources requiring access-control bypass.",
        f"- Can freeze formal provider now: {'No; a technical candidate exists, but authorization, retention, and redisplay rules are not confirmed' if has_technical_candidate else 'No; evidence is insufficient'}",
        "",
        "## Recommended Next Stage",
        "",
        "- Build a production announcement provider adapter only after product owner confirms authorization and retention rules.",
        "- Keep automatic news collection out of MVP unless rights and source stability are confirmed.",
    ]
    return "\n".join(lines) + "\n"
