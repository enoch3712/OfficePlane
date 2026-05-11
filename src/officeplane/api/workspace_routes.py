"""Workspace endpoints — read & write the agnostic Document JSON."""
import json
from pathlib import Path
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])

WORKSPACES_ROOT = Path("/data/workspaces")


@router.get("/{workspace_id}/document")
async def get_workspace_document(workspace_id: str):
    p = WORKSPACES_ROOT / workspace_id / "document.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="workspace document.json not found")
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=500, detail=f"invalid document.json: {e}")


@router.get("/{workspace_id}/output")
async def get_workspace_output_info(workspace_id: str):
    """Return paths to the rendered .docx / .pptx if present."""
    ws = WORKSPACES_ROOT / workspace_id
    if not ws.exists():
        raise HTTPException(status_code=404, detail="workspace not found")
    return {
        "workspace_id": workspace_id,
        "docx": str(ws / "output.docx") if (ws / "output.docx").exists() else None,
        "pptx": str(ws / "output.pptx") if (ws / "output.pptx").exists() else None,
        "document_json": str(ws / "document.json") if (ws / "document.json").exists() else None,
    }
