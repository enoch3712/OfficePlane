"""
ECM Instance routes — [MOCK]

An instance is a live session on a document (check-out equivalent).
Supports agent actions: run, plan, review, checkpoint.

POST   /api/ecm/instances                   open document → instance
GET    /api/ecm/instances/{id}              instance state
DELETE /api/ecm/instances/{id}              close instance
POST   /api/ecm/instances/{id}/run          run agent instruction on document
POST   /api/ecm/instances/{id}/plan         agent plans changes (read-only)
POST   /api/ecm/instances/{id}/review       agent reviews + annotates
POST   /api/ecm/instances/{id}/lock         acquire exclusive lock
POST   /api/ecm/instances/{id}/unlock       release lock
POST   /api/ecm/instances/{id}/checkpoint   save mid-run agent state
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/ecm/instances", tags=["ecm:instances"])

_MOCK = True


class OpenInstanceRequest(BaseModel):
    document_id: str
    mode: str = "read_write"  # "read_only" | "read_write"


class RunRequest(BaseModel):
    instruction: str
    model: Optional[str] = None
    driver: Optional[str] = None


class PlanRequest(BaseModel):
    instruction: str
    model: Optional[str] = None


class ReviewRequest(BaseModel):
    focus: Optional[str] = None  # e.g. "grammar", "structure", "completeness"
    model: Optional[str] = None


@router.post("", status_code=201)
async def open_instance(request: OpenInstanceRequest):
    return {
        "instance_id": f"inst_{uuid4().hex[:10]}",
        "document_id": request.document_id,
        "state": "open",
        "mode": request.mode,
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "locked_by": None,
        "_mock": _MOCK,
    }


@router.get("/{instance_id}")
async def get_instance(instance_id: str):
    return {
        "instance_id": instance_id,
        "document_id": "doc_placeholder",
        "state": "open",  # open | idle | in_use | closing | closed
        "mode": "read_write",
        "opened_at": datetime.now(timezone.utc).isoformat(),
        "locked_by": None,
        "last_activity": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }


@router.delete("/{instance_id}", status_code=204)
async def close_instance(instance_id: str):
    return None  # 204 No Content


@router.post("/{instance_id}/run", status_code=202)
async def run_on_instance(instance_id: str, request: RunRequest):
    job_id = f"job_{uuid4().hex[:10]}"
    return {
        "job_id": job_id,
        "instance_id": instance_id,
        "instruction": request.instruction,
        "status": "queued",
        "stream_url": f"/api/jobs/{job_id}/stream",
        "_mock": _MOCK,
    }


@router.post("/{instance_id}/plan")
async def plan_on_instance(instance_id: str, request: PlanRequest):
    return {
        "instance_id": instance_id,
        "plan": [
            {"step": 1, "action": "analyze_structure", "description": "Review current document structure"},
            {"step": 2, "action": "identify_gaps", "description": "Find sections that need changes"},
            {"step": 3, "action": "propose_edits", "description": "Draft specific changes"},
        ],
        "estimated_changes": 3,
        "risk": "low",  # low | medium | high
        "_mock": _MOCK,
    }


@router.post("/{instance_id}/review")
async def review_instance(instance_id: str, request: ReviewRequest):
    return {
        "instance_id": instance_id,
        "focus": request.focus or "general",
        "annotations": [
            {"section": "Introduction", "severity": "suggestion", "comment": "Could be more concise"},
            {"section": "Conclusion", "severity": "warning", "comment": "Missing summary of key points"},
        ],
        "score": 78,
        "passed": True,
        "_mock": _MOCK,
    }


@router.post("/{instance_id}/lock")
async def lock_instance(instance_id: str):
    return {
        "instance_id": instance_id,
        "locked": True,
        "locked_by": "current_user",
        "locked_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": None,
        "_mock": _MOCK,
    }


@router.post("/{instance_id}/unlock")
async def unlock_instance(instance_id: str):
    return {
        "instance_id": instance_id,
        "locked": False,
        "_mock": _MOCK,
    }


@router.post("/{instance_id}/checkpoint", status_code=201)
async def checkpoint_instance(instance_id: str):
    return {
        "checkpoint_id": f"ckpt_{uuid4().hex[:10]}",
        "instance_id": instance_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "resumable": True,
        "_mock": _MOCK,
    }
