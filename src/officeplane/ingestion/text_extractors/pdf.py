"""Extract per-page text from a PDF using PyMuPDF."""
from __future__ import annotations

import fitz


def extract_pdf_text(data: bytes) -> list[dict]:
    pages = []
    with fitz.open(stream=data, filetype="pdf") as doc:
        for i, page in enumerate(doc, start=1):
            pages.append({"page_number": i, "text": page.get_text("text") or ""})
    return pages
