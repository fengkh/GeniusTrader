from src.announcement.pdf_probe import inspect_pdf_bytes


def test_pdf_signature_detection():
    result = inspect_pdf_bytes(b"%PDF-1.4\n%%EOF")
    assert result["is_pdf_signature"] is True


def test_invalid_pdf_detection():
    result = inspect_pdf_bytes(b"not pdf")
    assert result["is_pdf_signature"] is False
    assert result["status"] == "PDF_UNAVAILABLE"
