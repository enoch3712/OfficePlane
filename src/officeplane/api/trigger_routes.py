"""Trigger + EventLog endpoints."""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from prisma import Json, Prisma
from pydantic import BaseModel, Field

from officeplane.events.bus import emit
from officeplane.events.jsonlogic_eval import apply as jl_apply

router = APIRouter(tags=["triggers"])
log = logging.getLogger("officeplane.api.triggers")


class TriggerSpec(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    event_type: str = Field(min_length=1, max_length=120)
    filter: dict[str, Any] = Field(default_factory=dict)
    pipeline_spec: dict[str, Any]
    status: str = Field(default="ENABLED", pattern="^(ENABLED|DISABLED)$")
    actor: str | None = None


class TriggerPatch(BaseModel):
    name: str | None = None
    description: str | None = None
    filter: dict[str, Any] | None = None
    pipeline_spec: dict[str, Any] | None = None
    status: str | None = Field(default=None, pattern="^(ENABLED|DISABLED)$")


class EmitRequest(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    source: str | None = None


class FilterTestRequest(BaseModel):
    filter: dict[str, Any]
    payload: dict[str, Any]


@router.get("/api/triggers")
async def list_triggers(event_type: str | None = None, status: str | None = None):
    db = Prisma()
    await db.connect()
    try:
        where: dict[str, Any] = {}
        if event_type:
            where["eventType"] = event_type
        if status:
            where["status"] = status
        rows = await db.trigger.find_many(where=where, order={"createdAt": "desc"})
        return {"triggers": [_to_dict(r) for r in rows]}
    finally:
        await db.disconnect()


@router.post("/api/triggers", status_code=201)
async def create_trigger(body: TriggerSpec):
    # Validate the pipeline_spec via the existing validator
    from officeplane.orchestration.pipeline import validate_spec
    try:
        validate_spec(body.pipeline_spec)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"invalid pipeline_spec: {e}")
    db = Prisma()
    await db.connect()
    try:
        row = await db.trigger.create(data={
            "name": body.name,
            "description": body.description,
            "eventType": body.event_type,
            "filter": Json(json.dumps(body.filter)),
            "pipelineSpec": Json(json.dumps(body.pipeline_spec)),
            "status": body.status,
            "actor": body.actor,
        })
        return _to_dict(row)
    finally:
        await db.disconnect()


@router.get("/api/triggers/{trigger_id}")
async def get_trigger(trigger_id: str):
    db = Prisma()
    await db.connect()
    try:
        r = await db.trigger.find_unique(where={"id": trigger_id})
        if not r:
            raise HTTPException(status_code=404, detail="trigger not found")
        return _to_dict(r, full=True)
    finally:
        await db.disconnect()


@router.patch("/api/triggers/{trigger_id}")
async def patch_trigger(trigger_id: str, body: TriggerPatch):
    db = Prisma()
    await db.connect()
    try:
        r = await db.trigger.find_unique(where={"id": trigger_id})
        if not r:
            raise HTTPException(status_code=404, detail="trigger not found")
        data: dict[str, Any] = {}
        if body.name is not None:
            data["name"] = body.name
        if body.description is not None:
            data["description"] = body.description
        if body.filter is not None:
            data["filter"] = Json(json.dumps(body.filter))
        if body.pipeline_spec is not None:
            from officeplane.orchestration.pipeline import validate_spec
            try:
                validate_spec(body.pipeline_spec)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=f"invalid pipeline_spec: {e}")
            data["pipelineSpec"] = Json(json.dumps(body.pipeline_spec))
        if body.status is not None:
            data["status"] = body.status
        if not data:
            return _to_dict(r, full=True)
        updated = await db.trigger.update(where={"id": trigger_id}, data=data)
        return _to_dict(updated, full=True)
    finally:
        await db.disconnect()


@router.delete("/api/triggers/{trigger_id}")
async def delete_trigger(trigger_id: str):
    db = Prisma()
    await db.connect()
    try:
        r = await db.trigger.find_unique(where={"id": trigger_id})
        if not r:
            raise HTTPException(status_code=404, detail="trigger not found")
        await db.trigger.delete(where={"id": trigger_id})
        return {"deleted": trigger_id}
    finally:
        await db.disconnect()


@router.post("/api/events/emit")
async def emit_event(body: EmitRequest):
    """Debug endpoint — emit a synthetic event."""
    ev_id = await emit(body.event_type, body.payload, source=body.source or "manual")
    return {"event_id": ev_id, "event_type": body.event_type}


@router.get("/api/events")
async def list_events(limit: int = Query(50, ge=1, le=500), event_type: str | None = None):
    db = Prisma()
    await db.connect()
    try:
        where: dict[str, Any] = {}
        if event_type:
            where["eventType"] = event_type
        rows = await db.eventlog.find_many(
            where=where, order={"createdAt": "desc"}, take=limit,
        )
        return {"events": [_event_to_dict(r) for r in rows]}
    finally:
        await db.disconnect()


@router.post("/api/triggers/test-filter")
async def test_filter(body: FilterTestRequest):
    """Dry-run a filter against a payload — for the trigger UI's 'try this' button."""
    try:
        result = jl_apply(body.filter, body.payload)
        return {"matched": bool(result), "result": result}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


def _to_dict(r, *, full: bool = False) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": r.id, "name": r.name, "description": r.description,
        "event_type": r.eventType, "status": r.status,
        "fire_count": r.fireCount,
        "last_fired_at": r.lastFiredAt.isoformat() if r.lastFiredAt else None,
        "created_at": r.createdAt.isoformat() if r.createdAt else None,
    }
    if full:
        filt = r.filter
        if isinstance(filt, str):
            try:
                filt = json.loads(filt)
            except Exception:
                filt = {}
        spec = r.pipelineSpec
        if isinstance(spec, str):
            try:
                spec = json.loads(spec)
            except Exception:
                spec = {}
        out["filter"] = filt or {}
        out["pipeline_spec"] = spec or {}
    return out


def _event_to_dict(r) -> dict[str, Any]:
    p = r.payload
    if isinstance(p, str):
        try:
            p = json.loads(p)
        except Exception:
            p = {}
    return {
        "id": r.id, "event_type": r.eventType, "payload": p or {},
        "source": r.source, "matched_trigger_ids": list(r.matchedTriggerIds or []),
        "created_at": r.createdAt.isoformat() if r.createdAt else None,
    }
