"""Per-format text extraction (no OCR)."""
from __future__ import annotations

from officeplane.ingestion.format_detector import DocumentFormat
from officeplane.ingestion.text_extractors.docx import extract_docx_text
from officeplane.ingestion.text_extractors.pdf import extract_pdf_text
from officeplane.ingestion.text_extractors.pptx import extract_pptx_text


def extract_text(data: bytes, doc_format: DocumentFormat) -> list[dict]:
    if doc_format == DocumentFormat.PDF:
        return extract_pdf_text(data)
    if doc_format in (DocumentFormat.DOCX, DocumentFormat.DOC):
        return extract_docx_text(data)
    if doc_format in (DocumentFormat.PPTX, DocumentFormat.PPT):
        return extract_pptx_text(data)
    raise ValueError(f"unsupported format for text extraction: {doc_format}")


__all__ = ["extract_text", "extract_pdf_text", "extract_docx_text", "extract_pptx_text"]
