"""Tests for the per-format text extractors (Phase 9)."""
from __future__ import annotations

from pathlib import Path

import pytest

from officeplane.ingestion.format_detector import DocumentFormat
from officeplane.ingestion.text_extractors import extract_text


def test_pptx_extraction_returns_per_slide_text():
    """Use the existing test.pptx fixture."""
    pptx_bytes = (Path(__file__).resolve().parents[1] / "test.pptx").read_bytes()
    pages = extract_text(pptx_bytes, DocumentFormat.PPTX)
    assert len(pages) >= 1
    assert all("page_number" in p for p in pages)
    assert all(isinstance(p.get("text", ""), str) for p in pages)


def test_docx_extraction_yields_at_least_one_page():
    docx_bytes = (Path(__file__).resolve().parents[1] / "test.docx").read_bytes()
    pages = extract_text(docx_bytes, DocumentFormat.DOCX)
    assert len(pages) >= 1


def test_unsupported_format_raises():
    with pytest.raises(ValueError):
        extract_text(b"not really data", DocumentFormat.UNKNOWN)
