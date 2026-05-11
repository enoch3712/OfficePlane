"""POST /api/workspaces/{ws}/validate-citations — invoke citation-validator skill."""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(tags=["validator"])
log = logging.getLogger("officeplane.api.validator")


class ValidateRequest(BaseModel):
    similarity_threshold: float = Field(default=0.55, ge=0.0, le=1.0)


@router.post("/api/workspaces/{workspace_id}/validate-citations")
async def validate_citations(workspace_id: str, body: ValidateRequest | None = None):
    handler_path = Path(
        "/app/src/officeplane/content_agent/skills/citation-validator/handler.py"
    )
    if not handler_path.exists():
        handler_path = (
            Path(__file__).resolve().parents[3]
            / "src/officeplane/content_agent/skills/citation-validator/handler.py"
        )
    spec = importlib.util.spec_from_file_location("citation_validator_handler", handler_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        return await mod.execute(inputs={
            "workspace_id": workspace_id,
            "similarity_threshold": body.similarity_threshold if body else 0.55,
        })
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("citation-validator failed")
        raise HTTPException(status_code=500, detail=str(e))
