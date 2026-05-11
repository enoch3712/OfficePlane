"""Document lifecycle — status transitions + audit log."""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, HTTPException
from prisma import Prisma
from pydantic import BaseModel, Field

router = APIRouter(tags=["lifecycle"])
log = logging.getLogger("officeplane.api.lifecycle")

# Allowed transitions matrix
TRANSITIONS = {
    "DRAFT": {"REVIEW", "ARCHIVED"},
    "REVIEW": {"APPROVED", "DRAFT", "ARCHIVED"},
    "APPROVED": {"ARCHIVED", "REVIEW"},
    "ARCHIVED": set(),  # terminal
}

StatusLiteral = Literal["DRAFT", "REVIEW", "APPROVED", "ARCHIVED"]


class TransitionRequest(BaseModel):
    to_status: StatusLiteral
    actor: str | None = Field(default=None, max_length=128)
    note: str | None = Field(default=None, max_length=1000)


@router.post("/api/documents/{document_id}/transition")
async def transition_document_status(document_id: str, body: TransitionRequest):
    db = Prisma()
    await db.connect()
    try:
        doc = await db.document.find_unique(where={"id": document_id})
        if not doc:
            raise HTTPException(status_code=404, detail="document not found")
        current = doc.status
        allowed = TRANSITIONS.get(current, set())
        if body.to_status not in allowed:
            raise HTTPException(
                status_code=400,
                detail=f"transition not allowed: {current} → {body.to_status}. "
                       f"Valid from {current}: {sorted(allowed) or '(none — terminal)'}",
            )
        # Update + audit row
        updated = await db.document.update(
            where={"id": document_id},
            data={"status": body.to_status},
        )
        event = await db.documentstatusevent.create(data={
            "documentId": document_id,
            "fromStatus": current,
            "toStatus": body.to_status,
            "actor": body.actor,
            "note": body.note,
        })
        # Emit event-bus event
        try:
            from officeplane.events.bus import emit as _emit
            await _emit(
                "document.status_changed",
                {
                    "document_id": document_id,
                    "from_status": current,
                    "to_status": body.to_status,
                    "actor": body.actor,
                },
                source="lifecycle_routes",
            )
        except Exception as _e:
            log.warning("event emit failed after status transition: %s", _e)
        return {
            "document_id": document_id,
            "from_status": current,
            "to_status": body.to_status,
            "event_id": event.id,
            "created_at": event.createdAt.isoformat(),
        }
    finally:
        await db.disconnect()


@router.get("/api/documents/{document_id}/status-history")
async def get_status_history(document_id: str, limit: int = 50):
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be 1..500")
    db = Prisma()
    await db.connect()
    try:
        doc = await db.document.find_unique(where={"id": document_id})
        if not doc:
            raise HTTPException(status_code=404, detail="document not found")
        events = await db.documentstatusevent.find_many(
            where={"documentId": document_id},
            order={"createdAt": "desc"},
            take=limit,
        )
        return {
            "document_id": document_id,
            "current_status": doc.status,
            "events": [
                {
                    "id": e.id,
                    "from_status": e.fromStatus,
                    "to_status": e.toStatus,
                    "actor": e.actor,
                    "note": e.note,
                    "created_at": e.createdAt.isoformat(),
                }
                for e in events
            ],
        }
    finally:
        await db.disconnect()
