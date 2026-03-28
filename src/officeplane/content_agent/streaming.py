"""
SSE streaming for content generation agent events.

Uses Redis pub/sub so the worker (producer) and the HTTP handler (consumer)
are decoupled — works even across processes.  Falls back to in-process
asyncio.Queue if Redis is unavailable.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, AsyncGenerator, Dict

log = logging.getLogger("officeplane.content_agent.streaming")


class SSEManager:
    """Manages SSE event streams for generation jobs."""

    def __init__(self):
        # Fallback in-process queues (used when Redis is down)
        self._streams: dict[str, asyncio.Queue] = {}

    def create_stream(self, job_id: str) -> None:
        """Create a fallback in-process stream."""
        self._streams[job_id] = asyncio.Queue()

    def remove_stream(self, job_id: str) -> None:
        """Remove fallback stream."""
        self._streams.pop(job_id, None)

    async def push_event(self, job_id: str, event: str, data: Dict[str, Any]) -> None:
        """Publish an SSE event — Redis first, fallback to in-process queue."""
        try:
            from officeplane.management.redis_client import publish_sse_event
            await publish_sse_event(job_id, event, data)
        except Exception:
            # Redis unavailable — fall back to in-process queue
            queue = self._streams.get(job_id)
            if queue:
                await queue.put({"event": event, "data": data})

    async def event_generator(self, job_id: str) -> AsyncGenerator[str, None]:
        """Generate SSE-formatted events for a job. Tries Redis, falls back to queue."""
        try:
            async for msg in self._redis_generator(job_id):
                yield msg
        except Exception:
            async for msg in self._queue_generator(job_id):
                yield msg

    async def _redis_generator(self, job_id: str) -> AsyncGenerator[str, None]:
        """Subscribe to Redis pub/sub channel for this job."""
        from officeplane.management.redis_client import subscribe_sse_events

        async for payload in subscribe_sse_events(job_id):
            if payload["event"] == "_keepalive":
                yield ": keepalive\n\n"
                continue
            yield _format_sse(payload["event"], payload["data"])
            if payload["event"] in ("stop", "error"):
                break

    async def _queue_generator(self, job_id: str) -> AsyncGenerator[str, None]:
        """Fallback: read from in-process asyncio.Queue."""
        queue = self._streams.get(job_id)
        if not queue:
            yield _format_sse("error", {"message": "Stream not found"})
            return

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield _format_sse(event["event"], event["data"])
                    if event["event"] == "stop":
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        except asyncio.CancelledError:
            pass


def _format_sse(event: str, data: Dict[str, Any]) -> str:
    """Format data as an SSE message."""
    payload = json.dumps(data, default=str)
    return f"event: {event}\ndata: {payload}\n\n"


# Global SSE manager
sse_manager = SSEManager()
