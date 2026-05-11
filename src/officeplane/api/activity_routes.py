"""GET /api/activity — global feed of recent skill invocations across all docs."""
from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, Query
from prisma import Prisma

router = APIRouter(prefix="/api/activity", tags=["activity"])
log = logging.getLogger("officeplane.api.activity")


@router.get("")
async def get_activity_feed(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    skill: str | None = Query(None, description="Filter to a specific skill name"),
    status: str | None = Query(None, pattern="^(ok|error)$"),
    workspace_id: str | None = Query(None),
    since_minutes: int | None = Query(None, ge=1, le=60 * 24 * 30),
):
    where: dict[str, Any] = {}
    if skill:
        where["skill"] = skill
    if status:
        where["status"] = status
    if workspace_id:
        where["workspaceId"] = workspace_id

    db = Prisma()
    await db.connect()
    try:
        if since_minutes is not None:
            from datetime import datetime, timedelta, timezone
            cutoff = datetime.now(tz=timezone.utc) - timedelta(minutes=since_minutes)
            where["startedAt"] = {"gte": cutoff}

        total = await db.skillinvocation.count(where=where)
        rows = await db.skillinvocation.find_many(
            where=where,
            order={"startedAt": "desc"},
            take=limit,
            skip=offset,
        )

        # Skill name → count breakdown (limited to current filter window)
        # Cheap aggregate: group in Python from the same rows (capped at limit).
        # For an accurate global breakdown, we'd run a separate count-group-by, but for
        # the activity feed UI the per-page breakdown is fine.
        skill_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {"ok": 0, "error": 0}
        for r in rows:
            skill_counts[r.skill] = skill_counts.get(r.skill, 0) + 1
            status_counts[r.status] = status_counts.get(r.status, 0) + 1

        return {
            "total_count": total,
            "page_count": len(rows),
            "limit": limit,
            "offset": offset,
            "filters": {
                "skill": skill, "status": status, "workspace_id": workspace_id,
                "since_minutes": since_minutes,
            },
            "skill_counts_in_page": skill_counts,
            "status_counts_in_page": status_counts,
            "events": [_to_event(r) for r in rows],
        }
    finally:
        await db.disconnect()


@router.get("/skills")
async def list_known_skills():
    """List every distinct skill name we've ever logged — for filter UI."""
    db = Prisma()
    await db.connect()
    try:
        rows = await db.skillinvocation.find_many(distinct=["skill"])
        return {"skills": sorted({r.skill for r in rows})}
    finally:
        await db.disconnect()


def _to_event(r) -> dict[str, Any]:
    outputs = r.outputs
    if isinstance(outputs, str):
        try:
            outputs = json.loads(outputs)
        except json.JSONDecodeError:
            outputs = {}
    elif not isinstance(outputs, dict):
        outputs = {}
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
        "summary": _summarise(r.skill, r.status, outputs),
    }


def _summarise(skill: str, status: str, outputs: dict[str, Any]) -> str:
    if status == "error":
        return f"{skill} (error)"
    if skill == "generate-docx":
        return f"Generated Word doc · {outputs.get('title','Untitled')}" + (
            f" · {outputs['node_count']} nodes" if outputs.get("node_count") else ""
        )
    if skill == "generate-pptx":
        return f"Generated deck · {outputs.get('title','Untitled')}" + (
            f" · {outputs['slide_count']} slides" if outputs.get("slide_count") else ""
        )
    if skill == "generate-pdf":
        return f"Generated PDF · {outputs.get('title','Untitled')}"
    if skill == "generate-from-collection":
        return f"Combined deck · {outputs.get('title','Untitled')}" + (
            f" · {outputs.get('source_document_count', '?')} sources"
        )
    if skill == "document-edit":
        op = outputs.get("operation") or ""
        aff = outputs.get("affected_node_id") or ""
        return f"Edited · {op} {aff}".strip()
    if skill == "vector-search":
        return f"Semantic search · {outputs.get('count', 0)} hits"
    if skill == "auto-categorize":
        return f"Auto-categorize · {outputs.get('suggestion_count', 0)} suggestions"
    if skill == "citation-validator":
        return f"Validated · confidence {outputs.get('overall_confidence', 0):.2f} · {outputs.get('unsupported_count', 0)} unsupported"
    if skill == "rewrite-node":
        return f"Rewrote node · {outputs.get('node_id','')}"
    if skill == "grounded-chat":
        return f"Chat · {outputs.get('mode','?')} · {outputs.get('retrieval_count',0)} hits"
    return f"{skill}"
