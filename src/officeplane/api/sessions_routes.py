"""
ECM Session API — atomic multi-agent, multi-document operations.

POST   /api/sessions                  — create a session
GET    /api/sessions/{id}             — session state + jobs
POST   /api/sessions/{id}/jobs        — add a job to an open session
POST   /api/sessions/{id}/commit      — execute all jobs atomically (async, streams events)
POST   /api/sessions/{id}/rollback    — discard session
GET    /api/sessions/{id}/stream      — SSE stream aggregating all job events
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from officeplane.content_agent.streaming import sse_manager
from officeplane.ecm.session import ECMSession

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sessions", tags=["sessions"])

# In-memory session store.
# TODO: back with Redis or Postgres for persistence across restarts.
_sessions: dict[str, ECMSession] = {}


class CreateSessionRequest(BaseModel):
    workspace_root: Optional[str] = None


class AddJobRequest(BaseModel):
    skill: str = Field(..., description="Skill name, e.g. 'generate-pptx-quality'")
    prompt: str = Field(..., min_length=1, max_length=10000)
    driver: Optional[str] = None
    model: str = "gpt-4o"
    params: dict[str, Any] = Field(default_factory=dict)


@router.post("", status_code=201)
async def create_session(request: CreateSessionRequest):
    """Create a new ECM session."""
    kwargs: dict = {}
    if request.workspace_root:
        kwargs["workspace_root"] = request.workspace_root

    session = ECMSession(**kwargs)
    _sessions[session.session_id] = session
    return session.to_dict()


@router.get("/{session_id}")
async def get_session(session_id: str):
    """Get session state and job list."""
    session = _get_or_404(session_id)
    return session.to_dict()


@router.post("/{session_id}/jobs", status_code=201)
async def add_job(session_id: str, request: AddJobRequest):
    """Add a skill job to an open session."""
    session = _get_or_404(session_id)

    params = {"prompt": request.prompt, **request.params}
    try:
        job = session.add_job(
            skill_name=request.skill,
            params=params,
            driver=request.driver,
            model=request.model,
        )
    except (RuntimeError, KeyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return {
        "job_id": job.job_id,
        "skill": job.skill_name,
        "driver": job.driver,
        "state": job.state,
    }


@router.post("/{session_id}/commit", status_code=202)
async def commit_session(session_id: str, background_tasks: BackgroundTasks):
    """
    Execute all session jobs atomically.

    Long-running — returns immediately. Subscribe to /stream for live events.
    All jobs succeed or all roll back.
    """
    session = _get_or_404(session_id)

    if session.state.value != "open":
        raise HTTPException(
            status_code=409,
            detail=f"Session is {session.state.value}, not open",
        )
    if not session.jobs:
        raise HTTPException(status_code=400, detail="Session has no jobs to commit")

    stream_id = f"session_{session_id}"
    sse_manager.create_stream(stream_id)

    background_tasks.add_task(_run_commit, session, stream_id)

    return {
        "session_id": session_id,
        "status": "running",
        "job_count": len(session.jobs),
        "stream_url": f"/api/sessions/{session_id}/stream",
    }


@router.post("/{session_id}/rollback")
async def rollback_session(session_id: str):
    """Discard a session and clean up all staging state."""
    session = _get_or_404(session_id)
    await session.rollback()
    _sessions.pop(session_id, None)
    return {"session_id": session_id, "status": "rolled_back"}


@router.get("/{session_id}/stream")
async def stream_session_events(session_id: str):
    """SSE stream aggregating events from all jobs in the session."""
    stream_id = f"session_{session_id}"
    if stream_id not in sse_manager._streams:
        sse_manager.create_stream(stream_id)

    return StreamingResponse(
        sse_manager.event_generator(stream_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_404(session_id: str) -> ECMSession:
    session = _sessions.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


async def _run_commit(session: ECMSession, stream_id: str) -> None:
    """Background task: run commit and emit final result event."""
    try:
        result = await session.commit()
        event = "session_committed" if result.succeeded else "session_failed"
        await sse_manager.push_event(
            stream_id,
            event,
            {
                "session_id": result.session_id,
                "status": result.status,
                "jobs": [
                    {
                        "job_id": j.job_id,
                        "skill": j.skill_name,
                        "state": j.state,
                        "result": j.result,
                        "error": j.error,
                    }
                    for j in result.jobs
                ],
                "errors": result.errors,
            },
        )
    except Exception as exc:
        log.error("Session commit error: %s", exc, exc_info=True)
        await sse_manager.push_event(
            stream_id,
            "session_failed",
            {"session_id": session.session_id, "error": str(exc)},
        )
    finally:
        await asyncio.sleep(1)  # give clients time to read the final event
        sse_manager.remove_stream(stream_id)
