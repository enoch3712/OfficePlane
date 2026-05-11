"""Records management — retention policies + legal hold + disposition."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from prisma import Prisma
from pydantic import BaseModel, Field

from officeplane.retention.policy import compute_due_at, compute_start_at
from officeplane.retention.disposition import run_disposition_pass

router = APIRouter(tags=["retention"])
log = logging.getLogger("officeplane.api.retention")


class CreatePolicyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    duration_days: int = Field(ge=1, le=365 * 100)
    action: str = Field(default="REVIEW", pattern="^(ARCHIVE|DESTROY|REVIEW)$")
    start_trigger: str = Field(default="created_at", pattern="^(created_at|status_approved|manual)$")


class ApplyPolicyRequest(BaseModel):
    policy_id: str
    actor: str | None = None
    start_at: datetime | None = None  # override; default = compute from policy


class LegalHoldRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=500)
    actor: str | None = None


@router.get("/api/retention/policies")
async def list_policies():
    db = Prisma(); await db.connect()
    try:
        rows = await db.retentionpolicy.find_many(order={"name": "asc"})
        return {"policies": [_policy_to_dict(r) for r in rows]}
    finally:
        await db.disconnect()


@router.post("/api/retention/policies", status_code=201)
async def create_policy(body: CreatePolicyRequest):
    db = Prisma(); await db.connect()
    try:
        existing = await db.retentionpolicy.find_unique(where={"name": body.name})
        if existing:
            raise HTTPException(status_code=409, detail="policy name already exists")
        row = await db.retentionpolicy.create(data={
            "name": body.name,
            "description": body.description,
            "durationDays": body.duration_days,
            "action": body.action,
            "startTrigger": body.start_trigger,
        })
        return _policy_to_dict(row)
    finally:
        await db.disconnect()


@router.delete("/api/retention/policies/{policy_id}")
async def delete_policy(policy_id: str):
    db = Prisma(); await db.connect()
    try:
        # Block delete if any document still bound to it
        in_use = await db.documentretention.count(where={"policyId": policy_id})
        if in_use > 0:
            raise HTTPException(
                status_code=409,
                detail=f"policy in use by {in_use} document(s); detach first",
            )
        existing = await db.retentionpolicy.find_unique(where={"id": policy_id})
        if not existing:
            raise HTTPException(status_code=404, detail="policy not found")
        await db.retentionpolicy.delete(where={"id": policy_id})
        return {"deleted": policy_id}
    finally:
        await db.disconnect()


@router.post("/api/documents/{document_id}/retention", status_code=201)
async def apply_policy_to_document(document_id: str, body: ApplyPolicyRequest):
    db = Prisma(); await db.connect()
    try:
        doc = await db.document.find_unique(where={"id": document_id})
        if not doc:
            raise HTTPException(status_code=404, detail="document not found")
        policy = await db.retentionpolicy.find_unique(where={"id": body.policy_id})
        if not policy:
            raise HTTPException(status_code=404, detail="policy not found")

        # Idempotent: if already attached, return existing
        existing = await db.documentretention.find_first(
            where={"documentId": document_id, "policyId": body.policy_id},
        )
        if existing:
            return _retention_to_dict(existing, policy_name=policy.name)

        # Compute dates
        if body.start_at is not None:
            start_at = body.start_at if body.start_at.tzinfo else body.start_at.replace(tzinfo=timezone.utc)
        else:
            start_at = compute_start_at(policy.startTrigger, {
                "created_at": doc.createdAt,
            })
        due_at = compute_due_at(start_at, policy.durationDays)

        row = await db.documentretention.create(data={
            "documentId": document_id,
            "policyId": body.policy_id,
            "startAt": start_at,
            "dispositionDueAt": due_at,
            "actor": body.actor,
        })
        return _retention_to_dict(row, policy_name=policy.name)
    finally:
        await db.disconnect()


@router.get("/api/documents/{document_id}/retention")
async def get_document_retentions(document_id: str):
    db = Prisma(); await db.connect()
    try:
        doc = await db.document.find_unique(where={"id": document_id})
        if not doc:
            raise HTTPException(status_code=404, detail="document not found")
        rows = await db.documentretention.find_many(where={"documentId": document_id})
        out = []
        for r in rows:
            policy = await db.retentionpolicy.find_unique(where={"id": r.policyId})
            out.append(_retention_to_dict(r, policy_name=policy.name if policy else None,
                                          policy=policy))
        return {"document_id": document_id, "retentions": out}
    finally:
        await db.disconnect()


@router.delete("/api/documents/{document_id}/retention/{retention_id}")
async def detach_retention(document_id: str, retention_id: str):
    db = Prisma(); await db.connect()
    try:
        r = await db.documentretention.find_unique(where={"id": retention_id})
        if not r or r.documentId != document_id:
            raise HTTPException(status_code=404, detail="retention not found")
        await db.documentretention.delete(where={"id": retention_id})
        return {"detached": retention_id}
    finally:
        await db.disconnect()


@router.post("/api/retention/{retention_id}/legal-hold")
async def apply_legal_hold(retention_id: str, body: LegalHoldRequest):
    db = Prisma(); await db.connect()
    try:
        r = await db.documentretention.find_unique(where={"id": retention_id})
        if not r:
            raise HTTPException(status_code=404, detail="retention not found")
        updated = await db.documentretention.update(
            where={"id": retention_id},
            data={"legalHold": True, "legalHoldReason": body.reason},
        )
        # Audit: emit a SKIPPED-style event for transparency
        await db.dispositionevent.create(data={
            "retentionId": retention_id,
            "action": "REVIEW",
            "status": "SKIPPED",
            "reason": f"legal hold applied: {body.reason}",
            "actor": body.actor,
        })
        return _retention_to_dict(updated)
    finally:
        await db.disconnect()


@router.delete("/api/retention/{retention_id}/legal-hold")
async def release_legal_hold(retention_id: str, actor: str | None = None):
    db = Prisma(); await db.connect()
    try:
        r = await db.documentretention.find_unique(where={"id": retention_id})
        if not r:
            raise HTTPException(status_code=404, detail="retention not found")
        if not r.legalHold:
            raise HTTPException(status_code=409, detail="not currently on legal hold")
        updated = await db.documentretention.update(
            where={"id": retention_id},
            data={"legalHold": False, "legalHoldReason": None},
        )
        await db.dispositionevent.create(data={
            "retentionId": retention_id,
            "action": "REVIEW",
            "status": "SUCCESS",
            "reason": "legal hold released",
            "actor": actor,
        })
        return _retention_to_dict(updated)
    finally:
        await db.disconnect()


@router.post("/api/retention/disposition/run")
async def run_disposition(
    limit: int = Query(500, ge=1, le=5000),
    dry_run: bool = Query(False),
    actor: str = Query("system"),
):
    """Operator endpoint — find due records + apply disposition. Idempotent."""
    return await run_disposition_pass(actor=actor, limit=limit, dry_run=dry_run)


@router.get("/api/retention/disposition/events")
async def list_disposition_events(limit: int = Query(50, ge=1, le=500)):
    db = Prisma(); await db.connect()
    try:
        rows = await db.dispositionevent.find_many(
            order={"createdAt": "desc"}, take=limit,
        )
        return {"events": [_event_to_dict(r) for r in rows]}
    finally:
        await db.disconnect()


def _policy_to_dict(r) -> dict[str, Any]:
    return {
        "id": r.id, "name": r.name, "description": r.description,
        "duration_days": r.durationDays, "action": r.action,
        "start_trigger": r.startTrigger,
        "created_at": r.createdAt.isoformat() if r.createdAt else None,
    }


def _retention_to_dict(r, *, policy_name: str | None = None, policy=None) -> dict[str, Any]:
    out = {
        "id": r.id, "document_id": r.documentId, "policy_id": r.policyId,
        "policy_name": policy_name,
        "start_at": r.startAt.isoformat() if r.startAt else None,
        "disposition_due_at": r.dispositionDueAt.isoformat() if r.dispositionDueAt else None,
        "legal_hold": r.legalHold, "legal_hold_reason": r.legalHoldReason,
        "disposed": r.disposed,
        "disposed_at": r.disposedAt.isoformat() if r.disposedAt else None,
        "actor": r.actor,
    }
    if policy is not None:
        out["policy"] = _policy_to_dict(policy)
    return out


def _event_to_dict(r) -> dict[str, Any]:
    return {
        "id": r.id, "retention_id": r.retentionId, "action": r.action,
        "status": r.status, "reason": r.reason, "actor": r.actor,
        "created_at": r.createdAt.isoformat() if r.createdAt else None,
    }
