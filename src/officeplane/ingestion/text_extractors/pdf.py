"""Extract per-page text from a PDF using PyMuPDF.

Falls back to OCR (via the configured OCR provider) when a page has no text
layer — i.e. scanned / image-only PDFs. The threshold for "no text" is
OCR_MIN_TEXT_CHARS characters after stripping whitespace.

The ``force_ocr`` flag skips direct text extraction entirely and routes every
page through OCR (useful for debugging or when the caller knows the PDF is
fully scanned).
"""
from __future__ import annotations

import logging
from typing import Any

import fitz

log = logging.getLogger("officeplane.ingestion.pdf")

OCR_MIN_TEXT_CHARS = 50  # below this we consider a page image-only


def extract_pdf_text(data: bytes, *, force_ocr: bool = False) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    ocr_pages_count = 0
    with fitz.open(stream=data, filetype="pdf") as doc:
        for page_idx, page in enumerate(doc, start=1):
            text = page.get_text("text") if not force_ocr else ""
            ocr_used = False
            needs_ocr = force_ocr or len(text.strip()) < OCR_MIN_TEXT_CHARS
            if needs_ocr:
                try:
                    ocr_text = _ocr_page(page, fallback_text=text)
                    # Mark ocr_used=True if: (a) forced and OCR ran, or
                    # (b) auto-fallback and OCR produced meaningful content
                    if force_ocr or (ocr_text and len(ocr_text.strip()) >= OCR_MIN_TEXT_CHARS):
                        ocr_used = True
                        ocr_pages_count += 1
                    text = ocr_text
                except Exception as e:
                    log.warning("OCR fallback failed on page %d: %s", page_idx, e)
            pages.append({
                "page_number": page_idx,
                "content": text or "",
                "metadata": {"ocr_used": ocr_used},
            })

    if ocr_pages_count:
        log.info("PDF ingested with OCR on %d/%d pages", ocr_pages_count, len(pages))
    return pages


def _ocr_page(page: Any, *, fallback_text: str = "") -> str:
    """Render the page to a PNG, OCR it via the configured provider."""
    from officeplane.ingestion.ocr import get_ocr_provider
    provider = get_ocr_provider()
    if not provider.available:
        return fallback_text  # silent skip if OCR not available
    pix = page.get_pixmap(dpi=200)
    png_bytes = pix.tobytes("png")
    return provider.extract_text(png_bytes)
