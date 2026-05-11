"""Tests for the PDF renderer (Phase 17 — pdf_render.py)."""
import io
import pytest
from officeplane.content_agent.renderers.document import parse_document
from officeplane.content_agent.renderers.pdf_render import render_pdf


def test_render_pdf_produces_valid_pdf_bytes(tmp_path):
    doc = parse_document({
        "type": "document",
        "meta": {"title": "Test PDF"},
        "children": [
            {"type": "section", "level": 1, "heading": "Intro", "children": [
                {"type": "paragraph", "text": "Hello world."}
            ]}
        ],
    })
    blob = render_pdf(doc, workspace_dir=tmp_path)
    assert isinstance(blob, bytes)
    assert blob.startswith(b"%PDF")
    assert len(blob) > 2000  # real PDF is at least 2KB


def test_render_pdf_handles_tables_and_figures(tmp_path, monkeypatch):
    monkeypatch.setenv("OFFICEPLANE_IMAGE_PROVIDER", "placeholder")
    doc = parse_document({
        "type": "document",
        "meta": {"title": "Rich"},
        "children": [
            {"type": "table", "headers": ["A", "B"], "rows": [["1", "2"], ["3", "4"]]},
            {"type": "figure", "id": "f1", "prompt": "test diagram", "caption": "Fig 1"},
        ],
    })
    blob = render_pdf(doc, workspace_dir=tmp_path)
    assert blob.startswith(b"%PDF")
    # Confirm placeholder image was generated alongside
    assert (tmp_path / "images" / "f1.png").exists()
