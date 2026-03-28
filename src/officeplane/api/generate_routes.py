"""
Content generation API routes.

Provides endpoints for generating presentations and documents
using the content generation agent.
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from officeplane.api.websocket import broadcast_document_event, broadcast_task_event
from officeplane.content_agent.config import ContentAgentConfig
from officeplane.content_agent.models import (
    GenerateRequest,
    GenerateResponse,
    JobState,
    JobStatus,
)
from officeplane.content_agent.runner import ContentAgentRunner
from officeplane.content_agent.streaming import sse_manager
from officeplane.management.task_queue import task_queue

log = logging.getLogger("officeplane.api.generate_routes")

router = APIRouter(prefix="/api/generate", tags=["generate"])

# In-memory job tracking (task queue handles persistence)
_jobs: dict[str, dict] = {}


@router.post("", status_code=202, response_model=GenerateResponse)
async def start_generation(request: GenerateRequest):
    """Start a content generation job."""
    # Enqueue task
    task = await task_queue.enqueue_task(
        task_type="content_generate",
        payload={
            "prompt": request.prompt,
            "output_format": request.output_format.value,
            "model": request.model,
            "options": request.options,
            "driver": request.driver.value,
        },
        task_name=f"Generate: {request.prompt[:60]}",
        priority="NORMAL",
        max_retries=1,
    )

    job_id = task["id"]

    # Create SSE stream
    sse_manager.create_stream(job_id)

    # Track job locally
    _jobs[job_id] = {
        "status": JobState.QUEUED,
        "created_at": datetime.utcnow(),
        "prompt": request.prompt,
    }

    await broadcast_task_event(job_id, "content_generate_queued", {
        "prompt": request.prompt[:100],
        "output_format": request.output_format.value,
    })

    return GenerateResponse(
        job_id=job_id,
        status=JobState.QUEUED,
        stream_url=f"/api/generate/{job_id}/stream",
    )


@router.get("/{job_id}/stream")
async def stream_events(job_id: str):
    """SSE endpoint for streaming generation events."""
    if job_id not in _jobs and not await task_queue.get_task(job_id):
        raise HTTPException(status_code=404, detail="Job not found")

    # Ensure stream exists
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


@router.get("/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """Get the current status of a generation job."""
    task = await task_queue.get_task(job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    # Map task state to job state
    state_map = {
        "QUEUED": JobState.QUEUED,
        "RUNNING": JobState.RUNNING,
        "COMPLETED": JobState.COMPLETED,
        "FAILED": JobState.FAILED,
        "CANCELLED": JobState.CANCELLED,
        "RETRYING": JobState.RUNNING,
    }

    result = task.get("result") or {}
    return JobStatus(
        job_id=job_id,
        status=state_map.get(task["state"], JobState.QUEUED),
        created_at=task["createdAt"],
        started_at=task.get("startedAt"),
        completed_at=task.get("completedAt"),
        document_id=result.get("document_id"),
        error=task.get("errorMessage"),
    )


@router.delete("/{job_id}")
async def cancel_job(job_id: str):
    """Cancel a generation job and clean up."""
    task = await task_queue.get_task(job_id)
    if not task:
        raise HTTPException(status_code=404, detail="Job not found")

    if task["state"] in ("COMPLETED", "FAILED", "CANCELLED"):
        raise HTTPException(status_code=409, detail=f"Job already {task['state'].lower()}")

    await task_queue.cancel_task(job_id)

    # Clean up SSE stream
    sse_manager.remove_stream(job_id)

    # Clean up workspace
    config = ContentAgentConfig.from_env()
    from officeplane.content_agent.workspace import WorkspaceManager
    WorkspaceManager(config.workspace_root).cleanup(job_id)

    # Remove local tracking
    _jobs.pop(job_id, None)

    await broadcast_task_event(job_id, "content_generate_cancelled", {})

    return {"job_id": job_id, "status": "cancelled"}
