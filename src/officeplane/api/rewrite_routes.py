"""POST /api/workspaces/{ws}/rewrite-node — invoke rewrite-node skill."""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(tags=["rewrite"])
log = logging.getLogger("officeplane.api.rewrite")


class RewriteRequest(BaseModel):
    node_id: str
    instruction: str
    tone: str | None = None


@router.post("/api/workspaces/{workspace_id}/rewrite-node")
async def rewrite_node(workspace_id: str, body: RewriteRequest):
    handler_path = Path(
        "/app/src/officeplane/content_agent/skills/rewrite-node/handler.py"
    )
    if not handler_path.exists():
        handler_path = (
            Path(__file__).resolve().parents[3]
            / "src/officeplane/content_agent/skills/rewrite-node/handler.py"
        )
    spec = importlib.util.spec_from_file_location("rewrite_node_handler", handler_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    try:
        return await mod.execute(inputs={
            "workspace_id": workspace_id,
            "node_id": body.node_id,
            "instruction": body.instruction,
            "tone": body.tone,
        })
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.exception("rewrite-node failed")
        raise HTTPException(status_code=500, detail=str(e))
