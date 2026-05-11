"""Event bus — emit named events with CloudEvents-shape payload.

emit() always persists to event_logs table; if Redis broker is configured,
also publishes to a redis channel for any in-process subscribers.
Subscribers can also register an in-process async handler via on().
"""
from __future__ import annotations

import asyncio
import logging
import os
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable
from uuid import uuid4

from prisma import Json, Prisma

log = logging.getLogger("officeplane.events.bus")


EventHandler = Callable[[dict[str, Any]], Awaitable[None]]

_handlers: dict[str, list[EventHandler]] = defaultdict(list)


def on(event_type: str, handler: EventHandler) -> None:
    """Register an in-process async handler for an event type. Glob '*' = all events."""
    _handlers[event_type].append(handler)


async def emit(event_type: str, payload: dict[str, Any], *, source: str | None = None) -> str:
    """Emit a named event.

    Persists to event_logs and notifies all in-process handlers. Returns the event id.
    Failures in any handler are logged and swallowed — never break the emitter.
    """
    event = {
        "id": uuid4().hex,
        "type": event_type,
        "time": datetime.now(tz=timezone.utc).isoformat(),
        "source": source or "officeplane",
        "data": payload,
    }

    # Persist to DB
    try:
        import json as _json
        db = Prisma()
        await db.connect()
        try:
            row = await db.eventlog.create(data={
                "eventType": event_type,
                "payload": Json(_json.dumps(payload)),
                "source": source,
            })
            event["id"] = row.id
        finally:
            await db.disconnect()
    except Exception as e:
        log.warning("event persistence failed: %s", e)

    # Notify in-process handlers
    fired_handlers = _handlers.get(event_type, []) + _handlers.get("*", [])
    for h in fired_handlers:
        try:
            result = h(event)
            if asyncio.iscoroutine(result):
                # Fire-and-forget, but don't lose exceptions silently
                asyncio.create_task(_safe_await(h, result, event_type))
        except Exception as e:
            log.warning("handler %s failed for %s: %s", h.__name__, event_type, e)
    return event["id"]


async def _safe_await(handler: EventHandler, coro, event_type: str) -> None:
    try:
        await coro
    except Exception as e:
        log.warning("handler %s failed (async) for %s: %s", handler.__name__, event_type, e)
