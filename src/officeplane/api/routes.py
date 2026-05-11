import base64
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Literal, Optional, Callable

from fastapi import APIRouter, UploadFile, File, HTTPException, Query
from fastapi.responses import Response, FileResponse
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST

from officeplane.core.limits import validate_upload, validate_dpi, DEFAULT_DPI
from officeplane.core.checksums import sha256_bytes
from officeplane.core.render import pdf_to_images, page_images_to_payload
from officeplane.core.versions import officeplane_version
from officeplane.observability.metrics import REQUESTS, FAILURES, CONVERT_SECONDS, RENDER_SECONDS
from officeplane.storage.local import LocalArtifactStore
from officeplane.drivers.mock_driver import MockDriver
from officeplane.drivers.base import OfficeDriver

log = logging.getLogger("officeplane.api")
router = APIRouter()

OUTPUT_MODE = os.getenv("OUTPUT_MODE", "inline").lower()
# Use /data in Docker, otherwise use a temp directory for local dev/testing
_default_data_dir = "/data" if os.path.isdir("/data") else tempfile.mkdtemp(prefix="officeplane_")
DATA_DIR = os.getenv("DATA_DIR", _default_data_dir)
store = LocalArtifactStore(DATA_DIR)

# Mock driver used for the legacy /render endpoint (DOCX→image pipeline)
driver: OfficeDriver = MockDriver()


@router.get("/health")
async def health():
    return {"status": "ok"}

@router.get("/metrics")
async def metrics():
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)

@router.get("/artifacts/{request_id}/{name}")
async def get_artifact(request_id: str, name: str):
    path = Path(DATA_DIR) / request_id / name
    if not path.exists():
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(str(path))

@router.post("/render")
async def render(
    file: UploadFile = File(...),
    dpi: int = Query(DEFAULT_DPI, ge=72, le=300),
    output: Literal["pdf", "images", "both"] = Query("both"),
    inline: bool = Query(True),
    image_format: Literal["png", "jpeg"] = Query("png"),
):
    t_total0 = time.time()

    filename = file.filename or "upload"
    input_bytes = await file.read()

    try:
        validate_upload(filename, len(input_bytes))
        dpi = validate_dpi(dpi)
    except ValueError as e:
        REQUESTS.labels(endpoint="/render", status="400", ext=os.path.splitext(filename)[1]).inc()
        raise HTTPException(status_code=400, detail=str(e))

    ext = os.path.splitext(filename.lower())[1]
    import uuid
    request_id = str(uuid.uuid4())

    try:
        t0 = time.time()
        with CONVERT_SECONDS.time():
            pdf_bytes = driver.convert_to_pdf(filename, input_bytes)
        convert_ms = int((time.time() - t0) * 1000)

        pdf_sha = sha256_bytes(pdf_bytes)

        t1 = time.time()
        with RENDER_SECONDS.time():
            images = pdf_to_images(pdf_bytes, dpi=dpi, fmt=image_format)
        render_ms = int((time.time() - t1) * 1000)

        use_inline = inline and OUTPUT_MODE == "inline"
        pages_payload = page_images_to_payload(images, inline=use_inline)

        pdf_out = None
        if output in ("pdf", "both"):
            if use_inline:
                pdf_out = {"sha256": pdf_sha, "base64": base64.b64encode(pdf_bytes).decode("utf-8")}
            else:
                url = store.put_bytes(request_id, "out.pdf", pdf_bytes, "application/pdf")
                pdf_out = {"sha256": pdf_sha, "url": url}

        if not use_inline:
            for i, img in enumerate(images):
                name = f"page_{img.page}.{image_format}"
                url = store.put_bytes(request_id, name, img.data, f"image/{image_format}")
                pages_payload[i]["url"] = url

        total_ms = int((time.time() - t_total0) * 1000)
        manifest = {
            "pages_count": len(images),
            "timings_ms": {"convert": convert_ms, "render": render_ms, "total": total_ms},
            "versions": {
                "officeplane": officeplane_version(),
            },
            "extra": {},
        }

        REQUESTS.labels(endpoint="/render", status="200", ext=ext).inc()

        return {
            "request_id": request_id,
            "input": {"filename": filename, "size_bytes": len(input_bytes)},
            "pdf": pdf_out,
            "pages": pages_payload if output in ("images", "both") else [],
            "manifest": manifest,
        }

    except Exception as e:
        FAILURES.labels(stage="render", reason=type(e).__name__).inc()
        REQUESTS.labels(endpoint="/render", status="500", ext=ext).inc()
        log.exception("render failed", extra={"filename": filename})
        raise HTTPException(status_code=500, detail=str(e))
