"""Extract text from a single uploaded image (.png/.jpg/.jpeg/.tiff) via OCR.

The image becomes the document's only "page".
"""
from __future__ import annotations

import logging
from typing import Any

from officeplane.ingestion.ocr import get_ocr_provider

log = logging.getLogger("officeplane.ingestion.image")


def extract_image_text(content: bytes) -> list[dict[str, Any]]:
    provider = get_ocr_provider()
    if not provider.available:
        # Soft-fail: produce one empty page so the document is at least ingested
        log.warning("OCR provider not available — image will have empty content")
        return [{"page_number": 1, "content": "", "metadata": {"ocr_used": False, "ocr_skipped": True}}]
    try:
        text = provider.extract_text(content)
    except Exception as e:
        log.warning("image OCR failed: %s", e)
        text = ""
    return [{
        "page_number": 1,
        "content": text or "",
        "metadata": {"ocr_used": bool(text), "extractor": "image+ocr"},
    }]
