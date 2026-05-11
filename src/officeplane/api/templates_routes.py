"""Workbook template endpoints."""
from __future__ import annotations

import importlib.util
import json
import logging
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/templates", tags=["templates"])
log = logging.getLogger("officeplane.api.templates")

TEMPLATES_ROOT = Path("/data/templates")


class SaveRequest(BaseModel):
    workspace_id: str
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None


class ApplyRequest(BaseModel):
    tables: dict[str, list[list[Any]]]
    title: str | None = None


def _root() -> Path:
    return Path(os.getenv("OFFICEPLANE_TEMPLATES_ROOT") or TEMPLATES_ROOT)


def _load(skill: str):
    p = Path(f"/app/src/officeplane/content_agent/skills/{skill}/handler.py")
    if not p.exists():
        p = Path(__file__).resolve().parents[3] / f"src/officeplane/content_agent/skills/{skill}/handler.py"
    spec = importlib.util.spec_from_file_location(f"{skill.replace('-', '_')}_handler", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@router.get("")
async def list_templates():
    root = _root()
    if not root.exists():
        return {"templates": []}
    items = []
    for f in sorted(root.glob("*.json")):
        try:
            d = json.loads(f.read_text())
            items.append({
                "template_id": d.get("template_id"),
                "name": d.get("name"),
                "description": d.get("description"),
                "created_at": d.get("created_at"),
                "from_workspace_id": d.get("from_workspace_id"),
                "table_count": sum(
                    1 for sh in (d.get("workbook", {}).get("sheets") or [])
                    for sec in (sh.get("sections") or [])
                    if sec.get("type") == "table"
                ),
            })
        except Exception as e:
            log.warning("skipping invalid template %s: %s", f, e)
    return {"templates": items}


@router.get("/{template_id}")
async def get_template(template_id: str):
    p = _root() / f"{template_id}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="template not found")
    return json.loads(p.read_text())


@router.delete("/{template_id}")
async def delete_template(template_id: str):
    p = _root() / f"{template_id}.json"
    if not p.exists():
        raise HTTPException(status_code=404, detail="template not found")
    p.unlink()
    return {"deleted": template_id}


@router.post("/save")
async def save_template(body: SaveRequest):
    mod = _load("xlsx-template-save")
    try:
        return await mod.execute(inputs={
            "workspace_id": body.workspace_id,
            "name": body.name,
            "description": body.description,
        })
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{template_id}/apply")
async def apply_template(template_id: str, body: ApplyRequest):
    mod = _load("xlsx-template-apply")
    try:
        return await mod.execute(inputs={
            "template_id": template_id,
            "tables": body.tables,
            "title": body.title,
        })
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
