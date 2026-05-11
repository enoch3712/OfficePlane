"""Signed download URLs for workspace output files.

Knowing a valid signed URL = permission to read the file. The URL embeds
an expiry timestamp and an HMAC computed over (workspace_id, filename, expiry)
using OFFICEPLANE_SIGNING_KEY (default: a stable dev key — overrideable per env).
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import mimetypes
import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

router = APIRouter(tags=["downloads"])
log = logging.getLogger("officeplane.api.signed_download")

WORKSPACES_ROOT = Path("/data/workspaces")
DEFAULT_KEY = "officeplane-dev-signing-key-change-in-prod"
DEFAULT_TTL = 3600  # 1h
MAX_TTL = 7 * 24 * 3600  # 7 days


def _signing_key() -> bytes:
    return (os.getenv("OFFICEPLANE_SIGNING_KEY") or DEFAULT_KEY).encode("utf-8")


def _sign(workspace_id: str, filename: str, expiry: int) -> str:
    """Compute HMAC-SHA256 over the tuple, return URL-safe hex."""
    msg = f"{workspace_id}|{filename}|{expiry}".encode("utf-8")
    return hmac.new(_signing_key(), msg, hashlib.sha256).hexdigest()


def _verify(workspace_id: str, filename: str, expiry: int, provided: str) -> bool:
    expected = _sign(workspace_id, filename, expiry)
    return hmac.compare_digest(expected, provided)


def _safe_filename(filename: str) -> str:
    """Reject path traversal attempts. Allow only basename-style names with one extension."""
    if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
        raise HTTPException(status_code=400, detail="invalid filename")
    if ".." in filename:
        raise HTTPException(status_code=400, detail="invalid filename")
    return filename


class SignRequest(BaseModel):
    file: str = Field(..., description="basename of the file under the workspace dir")
    ttl_seconds: int = Field(default=DEFAULT_TTL, ge=60, le=MAX_TTL)


class SignResponse(BaseModel):
    download_url: str
    expires_at: int
    workspace_id: str
    file: str


@router.post("/api/workspaces/{workspace_id}/sign", response_model=SignResponse)
def create_signed_url(workspace_id: str, body: SignRequest):
    filename = _safe_filename(body.file)
    workspace_dir = WORKSPACES_ROOT / workspace_id
    target = workspace_dir / filename
    if not workspace_dir.exists():
        raise HTTPException(status_code=404, detail="workspace not found")
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail=f"file not found: {filename}")

    expiry = int(time.time()) + body.ttl_seconds
    token = _sign(workspace_id, filename, expiry)

    base = os.getenv("OFFICEPLANE_API_PUBLIC_URL", "")  # optional override
    path = f"/api/workspaces/{workspace_id}/download/{filename}?token={token}&exp={expiry}"
    download_url = f"{base.rstrip('/')}{path}" if base else path

    return SignResponse(
        download_url=download_url,
        expires_at=expiry,
        workspace_id=workspace_id,
        file=filename,
    )


@router.get("/api/workspaces/{workspace_id}/download/{filename}")
def signed_download(
    workspace_id: str,
    filename: str,
    token: str,
    exp: int,
):
    safe_name = _safe_filename(filename)
    if int(time.time()) > exp:
        raise HTTPException(status_code=410, detail="link expired")
    if not _verify(workspace_id, safe_name, exp, token):
        raise HTTPException(status_code=403, detail="invalid signature")

    target = WORKSPACES_ROOT / workspace_id / safe_name
    if not target.exists() or not target.is_file():
        raise HTTPException(status_code=404, detail="file no longer exists")

    media_type, _ = mimetypes.guess_type(str(target))
    if not media_type:
        # Specific overrides for our output types
        if safe_name.endswith(".docx"):
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif safe_name.endswith(".pptx"):
            media_type = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        elif safe_name.endswith(".pdf"):
            media_type = "application/pdf"
        else:
            media_type = "application/octet-stream"

    return FileResponse(
        path=str(target),
        media_type=media_type,
        filename=safe_name,
    )
