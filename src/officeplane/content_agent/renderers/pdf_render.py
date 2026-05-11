"""PDF renderer — Document → DOCX → libreoffice → PDF bytes.

Reuses the existing libreoffice install already in the api image (no new pip deps).
For deterministic output across machines, callers should pass a workspace_dir so
embedded figures resolve consistently.
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from pathlib import Path

from officeplane.content_agent.renderers.document import Document
from officeplane.content_agent.renderers.docx_render import render_docx

log = logging.getLogger("officeplane.renderers.pdf")


def render_pdf(doc: Document, *, workspace_dir: Path | None = None, timeout: int = 120) -> bytes:
    """Render the agnostic Document tree to PDF bytes via libreoffice.

    Converts the Document tree to DOCX bytes first using :func:`render_docx`,
    then shells out to libreoffice in headless mode to convert the DOCX to PDF.
    The PDF bytes are returned and the temporary directory is cleaned up.

    Args:
        doc: The agnostic Document tree to render.
        workspace_dir: Optional directory for generated image output.  If
            omitted, ``/tmp`` is used so Figure blocks with a ``prompt`` can
            still produce images without a real workspace path.
        timeout: Seconds to allow libreoffice to complete conversion.
            Defaults to 120.

    Returns:
        Raw PDF bytes (starts with ``%PDF``).

    Raises:
        RuntimeError: If libreoffice fails, times out, or produces no output.
    """
    docx_bytes = render_docx(doc, workspace_dir=workspace_dir)
    with tempfile.TemporaryDirectory(prefix="op_pdf_") as tmpdir:
        tmp = Path(tmpdir)
        docx_path = tmp / "doc.docx"
        docx_path.write_bytes(docx_bytes)
        try:
            result = subprocess.run(
                [
                    "libreoffice", "--headless", "--norestore", "--nofirststartwizard",
                    "--convert-to", "pdf", "--outdir", str(tmp), str(docx_path),
                ],
                capture_output=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired as e:
            raise RuntimeError(f"libreoffice timed out after {timeout}s") from e
        if result.returncode != 0:
            raise RuntimeError(
                "libreoffice PDF conversion failed: "
                + result.stderr.decode("utf-8", errors="ignore")[:500]
            )
        pdf_path = tmp / "doc.pdf"
        if not pdf_path.exists():
            raise RuntimeError(
                "libreoffice exited 0 but did not produce doc.pdf "
                + f"(stderr: {result.stderr.decode('utf-8', errors='ignore')[:200]})"
            )
        data = pdf_path.read_bytes()
        # Sanity check: PDF magic bytes
        if not data.startswith(b"%PDF"):
            raise RuntimeError("output is not a valid PDF (missing %PDF header)")
        log.info("render_pdf: produced %d bytes for doc '%s'", len(data), doc.meta.title)
        return data
