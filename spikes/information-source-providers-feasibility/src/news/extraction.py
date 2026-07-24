from __future__ import annotations

import re
from html import unescape

from ..normalization import normalize_text


SCRIPT_STYLE_RE = re.compile(r"<(script|style)[^>]*>.*?</\\1>", re.I | re.S)
TAG_RE = re.compile(r"<[^>]+>")


def extract_text_from_html(html: str, *, max_chars: int = 8000) -> str:
    stripped = SCRIPT_STYLE_RE.sub(" ", html)
    text = TAG_RE.sub(" ", stripped)
    text = normalize_text(unescape(text))
    return text[:max_chars]


def extract_title_from_html(html: str) -> str | None:
    match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.I | re.S)
    return normalize_text(unescape(match.group(1))) if match else None
