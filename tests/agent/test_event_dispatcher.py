import asyncio
import json
import uuid

import pytest
from unittest.mock import AsyncMock, patch


@pytest.mark.asyncio
async def test_event_emit_persists_to_db():
    from officeplane.events.bus import emit
    from prisma import Prisma

    ev_id = await emit("test.event", {"foo": "bar"}, source="pytest")
    db = Prisma(); await db.connect()
    try:
        row = await db.eventlog.find_unique(where={"id": ev_id})
        assert row is not None
        assert row.eventType == "test.event"
        await db.eventlog.delete(where={"id": ev_id})
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_dispatcher_enqueues_pipeline_on_match():
    """Create a trigger with a filter that matches; emit the event; verify run_pipeline was called."""
    from prisma import Json, Prisma
    from officeplane.events.dispatcher import _on_any_event

    db = Prisma(); await db.connect()
    try:
        trigger = await db.trigger.create(data={
            "name": f"test-{uuid.uuid4().hex[:6]}",
            "eventType": "test.match",
            "filter": Json(json.dumps({"==": [{"var": "kind"}, "yes"]})),
            "pipelineSpec": Json(json.dumps({"steps": [{"skill": "noop", "inputs": {}}]})),
            "status": "ENABLED",
        })

        fake_runs: list[tuple] = []

        async def fake_run_pipeline(spec, parameters=None, actor=None, **_):
            fake_runs.append((spec, parameters, actor))
            return {"run_id": "x", "state": "SUCCESS"}

        # Use a unique event type to avoid interference from leftover DB state
        unique_event = f"test.match.{uuid.uuid4().hex[:8]}"
        await db.trigger.update(where={"id": trigger.id}, data={"eventType": unique_event})

        # Build a synthetic event dict — do NOT call emit() here because that would
        # trigger the global '*' handler (registered via register_dispatcher) which
        # would call _on_any_event a second time when we call it explicitly below.
        fake_event_id = uuid.uuid4().hex
        event = {"id": fake_event_id, "type": unique_event,
                 "data": {"kind": "yes"}, "source": "test", "time": ""}

        with patch("officeplane.events.dispatcher.run_pipeline", new=fake_run_pipeline):
            await _on_any_event(event)
            # Give the background task time to start
            await asyncio.sleep(0.2)

        assert len(fake_runs) == 1
        spec, params, actor = fake_runs[0]
        assert spec["steps"][0]["skill"] == "noop"
        assert params["trigger_id"] == trigger.id
        assert actor.startswith("trigger:")

        # Trigger fire_count should have bumped
        tr2 = await db.trigger.find_unique(where={"id": trigger.id})
        assert (tr2.fireCount or 0) >= 1

        # Cleanup
        await db.trigger.delete(where={"id": trigger.id})
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_dispatcher_skips_when_filter_doesnt_match():
    from prisma import Json, Prisma
    from officeplane.events.dispatcher import _on_any_event

    db = Prisma(); await db.connect()
    try:
        unique_event_nope = f"test.nope.{uuid.uuid4().hex[:8]}"
        trigger = await db.trigger.create(data={
            "name": f"test-{uuid.uuid4().hex[:6]}",
            "eventType": unique_event_nope,
            "filter": Json(json.dumps({"==": [{"var": "kind"}, "wanted"]})),
            "pipelineSpec": Json(json.dumps({"steps": [{"skill": "noop", "inputs": {}}]})),
            "status": "ENABLED",
        })

        fake_runs: list = []

        async def fake_run(spec, parameters=None, actor=None, **_):
            fake_runs.append(1)
            return {"run_id": "x"}

        fake_event_id2 = uuid.uuid4().hex
        with patch("officeplane.events.dispatcher.run_pipeline", new=fake_run):
            await _on_any_event({"id": fake_event_id2, "type": unique_event_nope,
                                 "data": {"kind": "different"}, "source": "test", "time": ""})
            await asyncio.sleep(0.2)

        assert len(fake_runs) == 0
        try:
            await db.trigger.delete(where={"id": trigger.id})
        except Exception:
            pass
    finally:
        await db.disconnect()
