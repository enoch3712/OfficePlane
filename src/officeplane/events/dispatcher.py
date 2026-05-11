"""On every event, evaluate active Triggers; for matches, enqueue a PipelineRun."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from prisma import Json, Prisma

from officeplane.events.bus import on
from officeplane.events.jsonlogic_eval import apply as jl_apply
from officeplane.orchestration.pipeline import run_pipeline

log = logging.getLogger("officeplane.events.dispatcher")


async def _on_any_event(event: dict[str, Any]) -> None:
    event_type = event.get("type") or ""
    data = event.get("data") or {}
    db = Prisma()
    try:
        await db.connect()
        triggers = await db.trigger.find_many(
            where={"eventType": event_type, "status": "ENABLED"},
        )
        matched_trigger_ids: list[str] = []
        for tr in triggers:
            filt = tr.filter
            if isinstance(filt, str):
                try:
                    filt = json.loads(filt)
                except json.JSONDecodeError:
                    filt = {}
            try:
                # Bind data under "event.data.*" so filter authors can use {"var": "document.tags"}
                # OR they can use {"var": "event.data.document.tags"} — support both shapes by
                # exposing the *data* dict as the root context and the full envelope as `event`.
                ctx = {**(data or {}), "event": event}
                if filt and not jl_apply(filt, ctx):
                    continue
            except Exception as e:
                log.warning("trigger %s filter eval failed: %s", tr.id, e)
                continue
            # Match → enqueue pipeline
            try:
                await _enqueue_pipeline(db, tr, event)
                matched_trigger_ids.append(tr.id)
            except Exception as e:
                log.warning("trigger %s pipeline enqueue failed: %s", tr.id, e)

        # Update the event_log row with matched_trigger_ids
        if matched_trigger_ids:
            try:
                await db.eventlog.update(
                    where={"id": event["id"]},
                    data={"matchedTriggerIds": matched_trigger_ids},
                )
            except Exception as e:
                log.debug("update event_log matched ids failed: %s", e)
    finally:
        try:
            await db.disconnect()
        except Exception:
            pass


async def _enqueue_pipeline(db: Prisma, trigger, event: dict[str, Any]) -> None:
    """Fire the trigger's pipeline_spec as a fresh pipeline run."""
    spec = trigger.pipelineSpec
    if isinstance(spec, str):
        spec = json.loads(spec)
    if not isinstance(spec, dict) or not spec.get("steps"):
        log.warning("trigger %s has invalid pipeline_spec", trigger.id)
        return

    # Parameters available to the pipeline: the event payload, exposed as ${parameters.event.*}
    parameters = {"event": event.get("data") or {}, "trigger_id": trigger.id}

    # Run in the background — don't block the dispatcher
    async def _bg():
        try:
            await run_pipeline(spec=spec, parameters=parameters, actor=f"trigger:{trigger.id}")
        except Exception as e:
            log.warning("trigger %s pipeline run failed: %s", trigger.id, e)

    asyncio.create_task(_bg())

    # Bump fire_count + last_fired_at
    try:
        from datetime import datetime, timezone
        await db.trigger.update(
            where={"id": trigger.id},
            data={"fireCount": (trigger.fireCount or 0) + 1,
                  "lastFiredAt": datetime.now(tz=timezone.utc)},
        )
    except Exception as e:
        log.debug("trigger update failed: %s", e)


def register_dispatcher() -> None:
    """Hook the dispatcher into the bus. Call once at app startup."""
    on("*", _on_any_event)
