"""POST /api/documents/{id}/auto-categorize — invoke the auto-categorize skill."""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["categorize"])
log = logging.getLogger("officeplane.api.categorize")


class CategorizeRequest(BaseModel):
    max_suggestions: int = 3


@router.post("/api/documents/{document_id}/auto-categorize")
async def auto_categorize(document_id: str, body: CategorizeRequest | None = None):
    handler_path = Path("/app/src/officeplane/content_agent/skills/auto-categorize/handler.py")
    if not handler_path.exists():
        handler_path = (
            Path(__file__).resolve().parents[3]
            / "src/officeplane/content_agent/skills/auto-categorize/handler.py"
        )
    spec = importlib.util.spec_from_file_location("auto_categorize_handler", handler_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        return await mod.execute(inputs={
            "document_id": document_id,
            "max_suggestions": (body.max_suggestions if body else 3),
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("auto-categorize failed")
        raise HTTPException(status_code=500, detail=str(e))
