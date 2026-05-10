"""Extract text from DOCX. Best-effort 'page' splitting via Heading 1 elements."""
from __future__ import annotations

import io

from docx import Document


def extract_docx_text(data: bytes) -> list[dict]:
    """Each Heading 1 starts a new logical 'page'. Falls back to the whole doc as page 1."""
    doc = Document(io.BytesIO(data))
    pages: list[dict] = []
    current_text: list[str] = []
    page_num = 1
    for para in doc.paragraphs:
        if para.style.name.startswith("Heading 1") and current_text:
            pages.append({"page_number": page_num, "text": "\n".join(current_text).strip()})
            page_num += 1
            current_text = []
        current_text.append(para.text)
    if current_text:
        pages.append({"page_number": page_num, "text": "\n".join(current_text).strip()})
    if not pages:
        pages = [{"page_number": 1, "text": ""}]
    return pages
