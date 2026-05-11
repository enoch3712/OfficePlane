"""
ECM Document routes — [PARTIAL MOCK]

Document-level ECM operations: metadata, permissions, audit, lifecycle,
renditions, relations, subscriptions, and agentic extras.

GET/PUT /api/ecm/documents/{id}/metadata
POST    /api/ecm/documents/{id}/classify
GET/PUT /api/ecm/documents/{id}/permissions
GET     /api/ecm/documents/{id}/audit             ← REAL (skill_invocations)
GET     /api/ecm/documents/{id}/diff/{v1}/{v2}
PUT     /api/ecm/documents/{id}/status
POST    /api/ecm/documents/{id}/archive
POST    /api/ecm/documents/{id}/restore
GET     /api/ecm/documents/{id}/preview
POST    /api/ecm/documents/{id}/export
GET     /api/ecm/documents/{id}/relations
POST    /api/ecm/documents/{id}/relations
DELETE  /api/ecm/documents/{id}/relations/{relation_id}
POST    /api/ecm/documents/{id}/subscriptions
DELETE  /api/ecm/documents/{id}/subscriptions/{sub_id}
GET     /api/ecm/documents/{id}/agent-history
POST    /api/ecm/documents/{id}/explain
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from prisma import Prisma
from pydantic import BaseModel

log = logging.getLogger("officeplane.api.ecm.documents")

router = APIRouter(prefix="/api/ecm/documents", tags=["ecm:documents"])

_MOCK = True


# ── Metadata ──────────────────────────────────────────────────────────────────

class MetadataUpdate(BaseModel):
    fields: dict[str, Any]


@router.get("/{document_id}/metadata")
async def get_metadata(document_id: str):
    return {
        "document_id": document_id,
        "fields": {
            "title": "Q4 Financial Report",
            "author": "Finance Team",
            "document_type": "report",
            "language": "en",
            "department": "Finance",
            "confidentiality": "internal",
            "created_at": "2026-01-01T00:00:00Z",
        },
        "_mock": _MOCK,
    }


@router.put("/{document_id}/metadata")
async def update_metadata(document_id: str, request: MetadataUpdate):
    return {
        "document_id": document_id,
        "fields": request.fields,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }


@router.post("/{document_id}/classify")
async def classify_document(document_id: str):
    return {
        "document_id": document_id,
        "classification": {
            "document_type": "financial_report",
            "topics": ["finance", "q4", "annual"],
            "confidentiality": "internal",
            "language": "en",
            "confidence": 0.94,
        },
        "_mock": _MOCK,
    }


# ── Permissions ───────────────────────────────────────────────────────────────

class PermissionsUpdate(BaseModel):
    acl: list[dict[str, Any]]


@router.get("/{document_id}/permissions")
async def get_permissions(document_id: str):
    return {
        "document_id": document_id,
        "acl": [
            {"principal": "user:alice", "role": "owner", "permissions": ["read", "write", "delete", "share"]},
            {"principal": "group:finance", "role": "editor", "permissions": ["read", "write"]},
            {"principal": "group:all", "role": "viewer", "permissions": ["read"]},
        ],
        "_mock": _MOCK,
    }


@router.put("/{document_id}/permissions")
async def update_permissions(document_id: str, request: PermissionsUpdate):
    return {
        "document_id": document_id,
        "acl": request.acl,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }


# ── Audit ─────────────────────────────────────────────────────────────────────

@router.get("/{document_id}/audit")
async def get_audit_log(
    document_id: str,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    db = Prisma()
    await db.connect()
    try:
        # 1. 404 if document missing
        doc = await db.document.find_unique(where={"id": document_id})
        if not doc:
            raise HTTPException(status_code=404, detail="document not found")

        # 2. Find workspaces that derived from this document
        derivations = await db.derivation.find_many(
            where={"sourceDocumentId": document_id},
        )
        workspace_ids = list({d.workspaceId for d in derivations if d.workspaceId})

        # 3. Pull invocations
        if not workspace_ids:
            return {"document_id": document_id, "total_count": 0, "events": []}

        where_clause: dict[str, Any] = {"workspaceId": {"in": workspace_ids}}

        total = await db.skillinvocation.count(where=where_clause)
        rows = await db.skillinvocation.find_many(
            where=where_clause,
            order={"startedAt": "desc"},
            take=limit,
            skip=offset,
        )

        events = [_invocation_to_event(r) for r in rows]
        return {"document_id": document_id, "total_count": total, "events": events}
    finally:
        await db.disconnect()


def _parse_outputs(raw: Any) -> dict[str, Any]:
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}
    if isinstance(raw, dict):
        return raw
    return {}


def _summarise(skill: str, status: str, outputs: dict[str, Any]) -> str:
    if status == "error":
        return f"{skill} (error)"
    if skill == "generate-docx":
        title = outputs.get("title") or "Untitled"
        n = outputs.get("node_count")
        return f"Generated Word doc · {title}" + (f" · {n} nodes" if n else "")
    if skill == "generate-pptx":
        title = outputs.get("title") or "Untitled"
        n = outputs.get("slide_count")
        return f"Generated deck · {title}" + (f" · {n} slides" if n else "")
    if skill == "document-edit":
        op = outputs.get("operation") or ""
        aff = outputs.get("affected_node_id") or ""
        return f"Edited document · {op} {aff}".strip()
    return f"{skill} ({status})"


def _invocation_to_event(r: Any) -> dict[str, Any]:
    outputs = _parse_outputs(r.outputs)
    summary = _summarise(r.skill, r.status, outputs)
    affected = outputs.get("affected_node_id")
    return {
        "id": r.id,
        "timestamp": r.startedAt.isoformat() if r.startedAt else None,
        "skill": r.skill,
        "model": r.model,
        "actor": r.actor,
        "status": r.status,
        "duration_ms": r.durationMs,
        "workspace_id": r.workspaceId,
        "error_message": r.errorMessage,
        "affected_node_id": affected,
        "summary": summary,
    }


# ── Diff ──────────────────────────────────────────────────────────────────────

@router.get("/{document_id}/diff/{v1}/{v2}")
async def get_diff(document_id: str, v1: str, v2: str):
    return {
        "document_id": document_id,
        "from_version": v1,
        "to_version": v2,
        "changes": [
            {"type": "modified", "section": "Introduction", "from": "Old intro text.", "to": "New intro text."},
            {"type": "added", "section": "Appendix B", "from": None, "to": "New appendix content."},
        ],
        "stats": {"added": 1, "modified": 1, "removed": 0},
        "_mock": _MOCK,
    }


# ── Lifecycle ─────────────────────────────────────────────────────────────────

class StatusUpdate(BaseModel):
    status: str  # draft | in_review | approved | published | archived


@router.put("/{document_id}/status")
async def update_status(document_id: str, request: StatusUpdate):
    return {
        "document_id": document_id,
        "status": request.status,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }


@router.post("/{document_id}/archive")
async def archive_document(document_id: str):
    return {
        "document_id": document_id,
        "status": "archived",
        "archived_at": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }


@router.post("/{document_id}/restore")
async def restore_document(document_id: str):
    return {
        "document_id": document_id,
        "status": "draft",
        "restored_at": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }


# ── Renditions ────────────────────────────────────────────────────────────────

@router.get("/{document_id}/preview")
async def get_preview(document_id: str, format: str = "pdf"):
    return {
        "document_id": document_id,
        "format": format,
        "url": f"/storage/renditions/{document_id}/preview.{format}",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": None,
        "_mock": _MOCK,
    }


class ExportRequest(BaseModel):
    format: str  # pdf | docx | pptx | html | md


@router.post("/{document_id}/export", status_code=202)
async def export_document(document_id: str, request: ExportRequest):
    job_id = f"export_{uuid4().hex[:10]}"
    return {
        "job_id": job_id,
        "document_id": document_id,
        "format": request.format,
        "status": "queued",
        "stream_url": f"/api/jobs/{job_id}/stream",
        "_mock": _MOCK,
    }


# ── Relations ─────────────────────────────────────────────────────────────────

class AddRelationRequest(BaseModel):
    target_document_id: str
    relation_type: str  # references | replaces | related_to | child_of | translation_of


@router.get("/{document_id}/relations")
async def get_relations(document_id: str):
    return {
        "document_id": document_id,
        "relations": [
            {"relation_id": "rel_001", "type": "references", "target_id": "doc_456", "target_title": "Source Data"},
            {"relation_id": "rel_002", "type": "replaces", "target_id": "doc_123", "target_title": "Old Report v1"},
        ],
        "_mock": _MOCK,
    }


@router.post("/{document_id}/relations", status_code=201)
async def add_relation(document_id: str, request: AddRelationRequest):
    return {
        "relation_id": f"rel_{uuid4().hex[:8]}",
        "document_id": document_id,
        "target_document_id": request.target_document_id,
        "relation_type": request.relation_type,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }


@router.delete("/{document_id}/relations/{relation_id}", status_code=204)
async def remove_relation(document_id: str, relation_id: str):
    return None


# ── Subscriptions ─────────────────────────────────────────────────────────────

class SubscribeRequest(BaseModel):
    webhook_url: Optional[str] = None  # if None, use SSE
    events: list[str] = ["document_modified", "version_created", "status_changed"]


@router.post("/{document_id}/subscriptions", status_code=201)
async def subscribe(document_id: str, request: SubscribeRequest):
    return {
        "subscription_id": f"sub_{uuid4().hex[:10]}",
        "document_id": document_id,
        "events": request.events,
        "delivery": "webhook" if request.webhook_url else "sse",
        "webhook_url": request.webhook_url,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }


@router.delete("/{document_id}/subscriptions/{subscription_id}", status_code=204)
async def unsubscribe(document_id: str, subscription_id: str):
    return None


# ── Agentic extras ────────────────────────────────────────────────────────────

@router.get("/{document_id}/agent-history")
async def get_agent_history(document_id: str, limit: int = 20):
    return {
        "document_id": document_id,
        "runs": [
            {
                "run_id": "run_001",
                "job_id": "job_abc",
                "instruction": "Improve the executive summary",
                "driver": "deepagents_cli",
                "status": "completed",
                "started_at": datetime.now(timezone.utc).isoformat(),
                "duration_ms": 12400,
                "changes_made": 2,
            }
        ],
        "total": 1,
        "_mock": _MOCK,
    }


class ExplainRequest(BaseModel):
    focus: Optional[str] = None  # e.g. "structure", "purpose", "key_points"


@router.post("/{document_id}/explain")
async def explain_document(document_id: str, request: ExplainRequest):
    return {
        "document_id": document_id,
        "focus": request.focus or "general",
        "explanation": "This is a mock explanation of the document content and structure.",
        "key_points": ["Point A", "Point B", "Point C"],
        "structure_summary": {"sections": 5, "pages": 12, "word_count": 3200},
        "_mock": _MOCK,
    }
