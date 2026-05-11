"""POST /api/documents/{id}/extract-tables — invoke extract-tabular-data skill."""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["extract"])
log = logging.getLogger("officeplane.api.extract")


class ExtractRequest(BaseModel):
    max_tables: int = Field(default=20, ge=1, le=100)
    hint: str | None = None


@router.post("/api/documents/{document_id}/extract-tables")
async def extract_tables_endpoint(document_id: str, body: ExtractRequest | None = None):
    handler_path = Path(
        "/app/src/officeplane/content_agent/skills/extract-tabular-data/handler.py"
    )
    if not handler_path.exists():
        handler_path = (
            Path(__file__).resolve().parents[3]
            / "src/officeplane/content_agent/skills/extract-tabular-data/handler.py"
        )
    spec = importlib.util.spec_from_file_location("extract_tabular_handler", handler_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        return await mod.execute(inputs={
            "document_id": document_id,
            "max_tables": (body.max_tables if body else 20),
            "hint": (body.hint if body else None),
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("extract-tabular-data failed")
        raise HTTPException(status_code=500, detail=str(e))
