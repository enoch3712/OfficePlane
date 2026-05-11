"""POST /api/templates/{template_id}/populate-from-sources — composed skill flow."""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["populate"])
log = logging.getLogger("officeplane.api.populate")


class PopulateRequest(BaseModel):
    source_document_ids: list[str] = Field(min_length=1)
    hint: str | None = None
    title: str | None = None
    mapping: dict[str, str] | None = None


@router.post("/api/templates/{template_id}/populate-from-sources")
async def populate_from_sources(template_id: str, body: PopulateRequest):
    handler_path = Path(
        "/app/src/officeplane/content_agent/skills/populate-xlsx-from-source/handler.py"
    )
    if not handler_path.exists():
        handler_path = (
            Path(__file__).resolve().parents[3]
            / "src/officeplane/content_agent/skills/populate-xlsx-from-source/handler.py"
        )
    spec = importlib.util.spec_from_file_location("populate_xlsx_handler", handler_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        return await mod.execute(inputs={
            "source_document_ids": body.source_document_ids,
            "template_id": template_id,
            "hint": body.hint,
            "title": body.title,
            "mapping": body.mapping or {},
        })
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("populate-from-sources failed")
        raise HTTPException(status_code=500, detail=str(e))
