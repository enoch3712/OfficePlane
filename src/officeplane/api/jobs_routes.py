"""
Skill-based job execution API.

POST   /api/jobs             — enqueue a skill job
GET    /api/jobs/{id}        — job status + result
GET    /api/jobs/{id}/stream — SSE live event stream
DELETE /api/jobs/{id}        — cancel
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from officeplane.content_agent.skill_executor import (
    SkillExecutor,
    SkillNotFoundError,
)
from officeplane.content_agent.streaming import sse_manager
from officeplane.management.task_queue import task_queue

log = logging.getLogger(__name__)

_executor = SkillExecutor()

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


class JobRequest(BaseModel):
    skill: str = Field(..., description="Skill name, e.g. 'generate-pptx-quality'")
    prompt: str = Field(..., min_length=1, max_length=10000)
    driver: Optional[str] = Field(
        None, description="Override the skill's default driver"
    )
    model: Optional[str] = None
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Skill-specific parameters (merged with prompt)",
    )


class JobResponse(BaseModel):
    job_id: str
    status: str
    skill: str
    stream_url: str


@router.post("", status_code=202, response_model=JobResponse)
async def start_job(request: JobRequest):
    """Enqueue a skill execution job."""
    try:
        _executor.get_skill(request.skill)
    except SkillNotFoundError:
        raise HTTPException(status_code=404, detail=f"Skill {request.skill!r} not found")

    params = {"prompt": request.prompt, **request.params}
    driver = request.driver or "deepagents_sdk"

    task = await task_queue.enqueue_task(
        task_type="skill_run",
        payload={
            "skill": request.skill,
            "params": params,
            "driver": driver,
            "model": request.model,
        },
        task_name=f"{request.skill}: {request.prompt[:60]}",
        priority="NORMAL",
        max_retries=1,
    )

    job_id = task["id"]
    sse_manager.create_stream(job_id)

    return JobResponse(
        job_id=job_id,
        status="queued",
        skill=request.skill,
        stream_url=f"/api/jobs/{job_id}/stream",
    )


@router.get("/{job_id}/stream")
async def stream_job_events(job_id: str):
    """SSE stream for a running job."""
    task = await task_queue.get_task(job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    if job_id not in sse_manager._streams:
        sse_manager.create_stream(job_id)

    return StreamingResponse(
        sse_manager.event_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/{job_id}")
async def get_job_status(job_id: str):
    """Get job status and result."""
    task = await task_queue.get_task(job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    payload = task.get("payload") or {}
    result = task.get("result") or {}

    return {
        "job_id": job_id,
        "skill": payload.get("skill"),
        "driver": payload.get("driver"),
        "status": task["state"].lower(),
        "created_at": task["createdAt"],
        "started_at": task.get("startedAt"),
        "completed_at": task.get("completedAt"),
        "result": result,
        "error": task.get("errorMessage"),
    }


@router.post("/run", status_code=202, response_model=JobResponse)
async def run(instruction: str, model: str | None = None, driver: str | None = None):
    """
    Core agent endpoint — thin wrapper around: deepagents --yes -n "<instruction>"

    For one-off instructions without a specific skill.
    """
    task = await task_queue.enqueue_task(
        task_type="agent_run",
        payload={
            "instruction": instruction,
            "driver": driver or "deepagents_cli",
            "model": model,
        },
        task_name=instruction[:80],
        priority="NORMAL",
        max_retries=1,
    )

    job_id = task["id"]
    sse_manager.create_stream(job_id)

    return JobResponse(
        job_id=job_id,
        status="queued",
        skill="agent_run",
        stream_url=f"/api/jobs/{job_id}/stream",
    )


@router.delete("/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a queued or running job."""
    task = await task_queue.get_task(job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    if task["state"] in ("COMPLETED", "FAILED", "CANCELLED"):
        raise HTTPException(
            status_code=409, detail=f"Job already {task['state'].lower()}"
        )

    await task_queue.cancel_task(job_id)
    sse_manager.remove_stream(job_id)
    return {"job_id": job_id, "status": "cancelled"}


class InvokeSkillRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    actor_id: Optional[str] = None
    document_id: Optional[str] = None


class InvokeSkillResponse(BaseModel):
    skill: str
    output: dict[str, Any]


@router.post("/invoke/{skill_name}", response_model=InvokeSkillResponse)
async def invoke_skill_sync(skill_name: str, request: InvokeSkillRequest):
    """Synchronously invoke a SKILL.md skill via the new executor.

    For read-only or fast skills (audit-query, document-search). Use the
    queued ``POST /api/jobs`` endpoint for long-running content generation.
    """
    from officeplane.content_agent.skill_executor import SkillInputError

    try:
        output = await _executor.invoke(
            skill_name,
            request.inputs,
            actor_id=request.actor_id,
            document_id=request.document_id,
        )
    except SkillNotFoundError:
        raise HTTPException(status_code=404, detail=f"Skill {skill_name!r} not found")
    except SkillInputError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return InvokeSkillResponse(skill=skill_name, output=output)
