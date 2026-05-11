"""PDF renderer — Document tree → DOCX bytes → Gotenberg → PDF bytes.

Uses Gotenberg's HTTP API for the DOCX→PDF step (Gotenberg internally wraps
LibreOffice, so output fidelity is identical to subprocess shell-out but the
call is async, non-blocking, and runs in its own container).
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import httpx

from officeplane.content_agent.renderers.document import Document
from officeplane.content_agent.renderers.docx_render import render_docx

log = logging.getLogger("officeplane.renderers.pdf")


GOTENBERG_URL = os.getenv("GOTENBERG_URL") or "http://gotenberg:3000"
CONVERT_PATH = "/forms/libreoffice/convert"


def render_pdf(doc: Document, *, workspace_dir: Path | None = None, timeout: int = 120) -> bytes:
    """Render Document → DOCX → Gotenberg → PDF bytes."""
    docx_bytes = render_docx(doc, workspace_dir=workspace_dir)
    files = {"files": ("doc.docx", docx_bytes,
                       "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(f"{GOTENBERG_URL}{CONVERT_PATH}", files=files)
    except httpx.RequestError as e:
        raise RuntimeError(
            f"Gotenberg unreachable at {GOTENBERG_URL}: {e}. "
            f"Is the gotenberg container running?"
        ) from e
    if resp.status_code != 200:
        raise RuntimeError(
            f"Gotenberg conversion failed: {resp.status_code} {resp.text[:300]}"
        )
    data = resp.content
    if not data.startswith(b"%PDF"):
        raise RuntimeError("Gotenberg response is not a PDF (missing %PDF header)")
    log.info("render_pdf: produced %d bytes for doc '%s'", len(data), doc.meta.title)
    return data
