"""POST /api/jobs/stream/{skill_name} — SSE-streamed skill execution.

Mirrors the existing /api/jobs/invoke/{skill_name} contract but instead of
returning a single JSON blob at the end, streams progress events as
text/event-stream:

    event: progress
    data: {"step":"loading_sources","label":"…","timestamp":1715454321}

    event: result
    data: {"file_path":"…","title":"…",...}

    event: done
    data: {}

On error:

    event: error
    data: {"detail":"…"}
"""
from __future__ import annotations

import asyncio
import importlib.util
import json
import logging
import sys
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from officeplane.content_agent.streaming import ProgressEvent

router = APIRouter(prefix="/api/jobs", tags=["streaming"])
log = logging.getLogger("officeplane.api.streaming")

SKILLS_ROOT = Path("/app/src/officeplane/content_agent/skills")


class InvokeBody(BaseModel):
    inputs: dict[str, Any] = {}


def _load_handler(skill_name: str):
    """Find and dynamically load a skill's handler.py.

    If the module is already registered in sys.modules (e.g. pre-loaded by a
    test with mocks applied), reuse it rather than reloading to preserve any
    monkey-patching the caller has set up.
    """
    mod_name = f"streamed_handler_{skill_name.replace('-', '_')}"
    if mod_name in sys.modules:
        return sys.modules[mod_name]

    # Try the in-container path first, then a fallback for dev
    candidates = [
        SKILLS_ROOT / skill_name / "handler.py",
        Path(__file__).resolve().parents[3] / "src/officeplane/content_agent/skills" / skill_name / "handler.py",
    ]
    for cand in candidates:
        if cand.exists():
            spec = importlib.util.spec_from_file_location(mod_name, cand)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
            return mod
    return None


def _sse(event: str, data: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode("utf-8")


@router.post("/stream/{skill_name}")
async def stream_skill(skill_name: str, body: InvokeBody, request: Request):
    handler = _load_handler(skill_name)
    if handler is None or not hasattr(handler, "execute"):
        raise HTTPException(status_code=404, detail=f"skill not found: {skill_name}")

    queue: asyncio.Queue[tuple[str, dict[str, Any]] | None] = asyncio.Queue()

    async def progress_cb(event: ProgressEvent):
        await queue.put(("progress", event.to_dict()))

    async def runner():
        try:
            result = await handler.execute(inputs=body.inputs, progress=progress_cb)
            await queue.put(("result", result if isinstance(result, dict) else {"output": result}))
        except Exception as e:
            log.exception("streamed skill %s failed", skill_name)
            await queue.put(("error", {"detail": str(e)}))
        finally:
            await queue.put(None)  # sentinel

    async def gen():
        task = asyncio.create_task(runner())
        try:
            while True:
                if await request.is_disconnected():
                    task.cancel()
                    break
                item = await queue.get()
                if item is None:
                    yield _sse("done", {})
                    break
                event_name, payload = item
                yield _sse(event_name, payload)
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except (asyncio.CancelledError, Exception):
                    pass

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
