"""POST /api/documents/{id}/detect-pii — invoke detect-pii skill."""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["pii"])
log = logging.getLogger("officeplane.api.pii")


class DetectPiiRequest(BaseModel):
    categories: list[str] | None = None
    regex_only: bool = False
    max_findings: int = Field(default=200, ge=1, le=1000)


@router.post("/api/documents/{document_id}/detect-pii")
async def detect_pii_endpoint(document_id: str, body: DetectPiiRequest | None = None):
    handler_path = Path("/app/src/officeplane/content_agent/skills/detect-pii/handler.py")
    if not handler_path.exists():
        handler_path = (
            Path(__file__).resolve().parents[3]
            / "src/officeplane/content_agent/skills/detect-pii/handler.py"
        )
    spec = importlib.util.spec_from_file_location("detect_pii_handler", handler_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    body = body or DetectPiiRequest()
    try:
        return await mod.execute(inputs={
            "document_id": document_id,
            "categories": body.categories,
            "regex_only": body.regex_only,
            "max_findings": body.max_findings,
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("detect-pii failed")
        raise HTTPException(status_code=500, detail=str(e))
