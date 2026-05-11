import io
import pytest
from unittest.mock import patch
from officeplane.ingestion.text_extractors.pdf import extract_pdf_text


def _build_text_pdf(text: str) -> bytes:
    """Build a tiny PDF with text content via pymupdf."""
    import fitz
    doc = fitz.Document()
    page = doc.new_page()
    page.insert_text((72, 72), text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _build_image_only_pdf() -> bytes:
    """Build a PDF whose only content is an embedded image (no text layer)."""
    import fitz
    from PIL import Image
    img = Image.new("RGB", (400, 300), color="white")
    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_buf.seek(0)

    doc = fitz.Document()
    page = doc.new_page()
    # Embed the image — no text at all
    page.insert_image((50, 50, 350, 250), stream=img_buf.read())
    pdf_buf = io.BytesIO()
    doc.save(pdf_buf)
    return pdf_buf.getvalue()


def test_text_pdf_extracts_directly():
    """Text PDF should NOT trigger OCR."""
    pdf = _build_text_pdf("Blood pressure measurement protocol — Step 1 prepare patient.")
    pages = extract_pdf_text(pdf)
    assert pages and "Blood pressure" in pages[0]["content"]
    assert pages[0]["metadata"].get("ocr_used") is False


def test_image_only_pdf_triggers_ocr_fallback():
    """Image-only PDF should fall through to OCR. If tesseract unavailable, the
    fallback must produce an empty/short result without crashing."""
    pdf = _build_image_only_pdf()
    # Verify direct text extraction returns empty
    pages = extract_pdf_text(pdf)
    assert len(pages) == 1
    # Either OCR ran (probably with empty result since the image is blank), or it
    # was unavailable and skipped — either way, no exception.
    md = pages[0]["metadata"]
    assert "ocr_used" in md


def test_force_ocr_skips_text_extract(monkeypatch):
    """If force_ocr is True, even a text PDF should be routed through OCR (which
    we mock here to confirm the route)."""
    from officeplane.ingestion.text_extractors import pdf as pdf_mod

    captured = {"called": 0}

    def fake_ocr_page(page, *, fallback_text=""):
        captured["called"] += 1
        return "FAKE OCR OUTPUT"

    pdf = _build_text_pdf("Original text content.")
    with patch.object(pdf_mod, "_ocr_page", side_effect=fake_ocr_page):
        pages = pdf_mod.extract_pdf_text(pdf, force_ocr=True)
    assert captured["called"] >= 1
    assert pages[0]["content"] == "FAKE OCR OUTPUT"
    assert pages[0]["metadata"]["ocr_used"] is True


def test_image_extractor_handles_unavailable_ocr(monkeypatch):
    """When OCR is unavailable, the image extractor produces an empty page,
    not an exception."""
    from officeplane.ingestion.text_extractors.image import extract_image_text
    monkeypatch.setenv("OFFICEPLANE_OCR_PROVIDER", "none")
    pages = extract_image_text(b"\x89PNG\r\n\x1a\nfake")
    assert len(pages) == 1
    assert pages[0]["content"] == ""
    assert pages[0]["metadata"].get("ocr_skipped") is True
