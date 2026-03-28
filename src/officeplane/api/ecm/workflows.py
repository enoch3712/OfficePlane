"""
ECM Workflow routes — [MOCK]

Approval and review workflows attached to documents.

GET    /api/ecm/workflows/definitions
POST   /api/ecm/documents/{id}/workflows
GET    /api/ecm/workflows/{id}
POST   /api/ecm/workflows/{id}/approve
POST   /api/ecm/workflows/{id}/reject
POST   /api/ecm/workflows/{id}/cancel
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["ecm:workflows"])

_MOCK = True


# ── Workflow definitions ───────────────────────────────────────────────────────

@router.get("/api/ecm/workflows/definitions")
async def list_workflow_definitions():
    return {
        "definitions": [
            {
                "definition_id": "wf_approval",
                "name": "Document Approval",
                "description": "Standard review and approval flow",
                "steps": ["review", "approve", "publish"],
            },
            {
                "definition_id": "wf_legal_review",
                "name": "Legal Review",
                "description": "Compliance and legal sign-off",
                "steps": ["legal_review", "compliance_check", "sign_off"],
            },
            {
                "definition_id": "wf_ai_review",
                "name": "AI-Assisted Review",
                "description": "Agent reviews then human approves",
                "steps": ["agent_review", "human_approval"],
            },
        ],
        "_mock": _MOCK,
    }


# ── Start workflow on a document ───────────────────────────────────────────────

class StartWorkflowRequest(BaseModel):
    definition_id: str
    assignees: list[str] = []
    due_date: Optional[str] = None
    notes: Optional[str] = None


@router.post("/api/ecm/documents/{document_id}/workflows", status_code=201)
async def start_workflow(document_id: str, request: StartWorkflowRequest):
    return {
        "workflow_id": f"wf_{uuid4().hex[:10]}",
        "document_id": document_id,
        "definition_id": request.definition_id,
        "state": "in_progress",
        "current_step": "review",
        "assignees": request.assignees,
        "due_date": request.due_date,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }


# ── Workflow instance operations ───────────────────────────────────────────────

@router.get("/api/ecm/workflows/{workflow_id}")
async def get_workflow(workflow_id: str):
    return {
        "workflow_id": workflow_id,
        "document_id": "doc_placeholder",
        "definition_id": "wf_approval",
        "state": "in_progress",  # in_progress | completed | rejected | cancelled
        "current_step": "review",
        "steps": [
            {"step": "review", "state": "completed", "completed_by": "user:alice", "completed_at": datetime.now(timezone.utc).isoformat()},
            {"step": "approve", "state": "pending", "assigned_to": "user:bob"},
            {"step": "publish", "state": "waiting"},
        ],
        "started_at": datetime.now(timezone.utc).isoformat(),
        "due_date": None,
        "_mock": _MOCK,
    }


class WorkflowActionRequest(BaseModel):
    comment: Optional[str] = None


@router.post("/api/ecm/workflows/{workflow_id}/approve")
async def approve_workflow_step(workflow_id: str, request: WorkflowActionRequest):
    return {
        "workflow_id": workflow_id,
        "action": "approved",
        "comment": request.comment,
        "next_step": "publish",
        "actioned_at": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }


@router.post("/api/ecm/workflows/{workflow_id}/reject")
async def reject_workflow_step(workflow_id: str, request: WorkflowActionRequest):
    return {
        "workflow_id": workflow_id,
        "action": "rejected",
        "comment": request.comment,
        "state": "rejected",
        "actioned_at": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }


@router.post("/api/ecm/workflows/{workflow_id}/cancel")
async def cancel_workflow(workflow_id: str, request: WorkflowActionRequest):
    return {
        "workflow_id": workflow_id,
        "action": "cancelled",
        "comment": request.comment,
        "state": "cancelled",
        "actioned_at": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }
