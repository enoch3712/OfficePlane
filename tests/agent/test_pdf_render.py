"""Tests for the PDF renderer (Phase 51 — Gotenberg HTTP path)."""
import pytest
from unittest.mock import patch, MagicMock


def test_render_pdf_calls_gotenberg(tmp_path):
    from officeplane.content_agent.renderers.document import parse_document
    from officeplane.content_agent.renderers import pdf_render

    doc = parse_document({
        "type": "document", "meta": {"title": "T"},
        "children": [{"type": "section", "level": 1, "heading": "X", "children": [
            {"type": "paragraph", "text": "Hi"}
        ]}],
    })

    fake_pdf = b"%PDF-1.7\n%fake pdf body\n%%EOF"
    fake_resp = MagicMock(status_code=200, content=fake_pdf)
    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.post = MagicMock(return_value=fake_resp)

    with patch.object(pdf_render.httpx, "Client", return_value=fake_client):
        blob = pdf_render.render_pdf(doc, workspace_dir=tmp_path)

    assert blob.startswith(b"%PDF")
    fake_client.post.assert_called_once()
    args, kwargs = fake_client.post.call_args
    assert "libreoffice/convert" in args[0]
    assert "files" in kwargs


def test_render_pdf_raises_on_gotenberg_unreachable(tmp_path):
    import httpx
    from officeplane.content_agent.renderers.document import parse_document
    from officeplane.content_agent.renderers import pdf_render

    doc = parse_document({"type": "document", "meta": {"title": "T"}, "children": []})

    class BoomClient:
        def __init__(self, *a, **kw): pass
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def post(self, *a, **kw):
            raise httpx.ConnectError("connection refused")

    with patch.object(pdf_render.httpx, "Client", BoomClient):
        try:
            pdf_render.render_pdf(doc, workspace_dir=tmp_path)
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "Gotenberg unreachable" in str(e)


def test_render_pdf_raises_on_bad_status(tmp_path):
    from officeplane.content_agent.renderers.document import parse_document
    from officeplane.content_agent.renderers import pdf_render

    doc = parse_document({"type": "document", "meta": {"title": "T"}, "children": []})

    fake_resp = MagicMock(status_code=500, text="internal server error")
    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.post = MagicMock(return_value=fake_resp)

    with patch.object(pdf_render.httpx, "Client", return_value=fake_client):
        try:
            pdf_render.render_pdf(doc, workspace_dir=tmp_path)
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "Gotenberg conversion failed" in str(e)


def test_render_pdf_raises_on_non_pdf_response(tmp_path):
    from officeplane.content_agent.renderers.document import parse_document
    from officeplane.content_agent.renderers import pdf_render

    doc = parse_document({"type": "document", "meta": {"title": "T"}, "children": []})

    fake_resp = MagicMock(status_code=200, content=b"not a pdf at all")
    fake_client = MagicMock()
    fake_client.__enter__ = MagicMock(return_value=fake_client)
    fake_client.__exit__ = MagicMock(return_value=False)
    fake_client.post = MagicMock(return_value=fake_resp)

    with patch.object(pdf_render.httpx, "Client", return_value=fake_client):
        try:
            pdf_render.render_pdf(doc, workspace_dir=tmp_path)
            assert False, "expected RuntimeError"
        except RuntimeError as e:
            assert "not a PDF" in str(e)
