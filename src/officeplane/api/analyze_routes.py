"""POST /api/documents/{id}/analyze-xlsx — invoke analyze-xlsx skill."""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["analyze"])
log = logging.getLogger("officeplane.api.analyze")


class AnalyzeXlsxRequest(BaseModel):
    max_issues: int = Field(default=20, ge=1, le=100)


@router.post("/api/documents/{document_id}/analyze-xlsx")
async def analyze_xlsx_endpoint(document_id: str, body: AnalyzeXlsxRequest | None = None):
    handler_path = Path(
        "/app/src/officeplane/content_agent/skills/analyze-xlsx/handler.py"
    )
    if not handler_path.exists():
        handler_path = (
            Path(__file__).resolve().parents[3]
            / "src/officeplane/content_agent/skills/analyze-xlsx/handler.py"
        )
    spec = importlib.util.spec_from_file_location("analyze_xlsx_handler", handler_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        return await mod.execute(inputs={
            "document_id": document_id,
            "max_issues": (body.max_issues if body else 20),
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("analyze-xlsx failed")
        raise HTTPException(status_code=500, detail=str(e))
