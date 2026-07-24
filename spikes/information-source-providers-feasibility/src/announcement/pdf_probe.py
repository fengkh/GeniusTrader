from __future__ import annotations

import io
from typing import Any

from ..http_client import SpikeHttpClient
from ..statuses import ProviderStatus


def inspect_pdf_bytes(content: bytes) -> dict[str, Any]:
    is_pdf = content.startswith(b"%PDF")
    result: dict[str, Any] = {
        "is_pdf_signature": is_pdf,
        "size_bytes": len(content),
        "page_count": None,
        "extractable_text_chars": None,
        "needs_ocr": None,
        "status": ProviderStatus.PDF_UNAVAILABLE.value if not is_pdf else ProviderStatus.PARTIAL.value,
        "limitations": [],
    }
    if not is_pdf:
        result["limitations"].append("content does not start with PDF signature")
        return result
    try:
        from pypdf import PdfReader  # type: ignore
    except Exception:
        result["limitations"].append("pypdf is not installed in the current interpreter")
        return result
    try:
        reader = PdfReader(io.BytesIO(content))
        result["page_count"] = len(reader.pages)
        text_chars = 0
        for page in reader.pages[:5]:
            text_chars += len(page.extract_text() or "")
        result["extractable_text_chars"] = text_chars
        result["needs_ocr"] = text_chars < 50
        result["status"] = ProviderStatus.PASS.value if text_chars >= 50 else ProviderStatus.PARTIAL.value
    except Exception as exc:
        result["status"] = ProviderStatus.PARSE_ERROR.value
        result["limitations"].append(exc.__class__.__name__)
    return result


def probe_pdf(client: SpikeHttpClient, url: str) -> dict[str, Any]:
    response = client.get(url)
    result = {
        "url": response.url,
        "http_status": response.status_code,
        "content_type": response.content_type,
        "content_length": response.content_length,
        "latency_ms": response.elapsed_ms,
        "error": response.error,
    }
    if not response.ok:
        result.update({"status": ProviderStatus.NETWORK_ERROR.value, "limitations": [response.error or str(response.status_code)]})
        return result
    result.update(inspect_pdf_bytes(response.content))
    return result
