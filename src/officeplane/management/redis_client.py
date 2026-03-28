"""
Backward-compatibility shim — delegates everything to the broker.

Existing code that imports from here still works.
New code should use `from officeplane.broker import get_broker` directly.
"""

from officeplane.broker import get_broker, close_broker


async def get_redis():
    """Returns the broker (not necessarily Redis)."""
    return await get_broker()


async def close_redis():
    await close_broker()


async def acquire_document_lock(document_id, holder, timeout=30.0):
    b = await get_broker()
    return await b.acquire_document_lock(document_id, holder, timeout)


async def release_document_lock(document_id, holder):
    b = await get_broker()
    return await b.release_document_lock(document_id, holder)


async def is_document_locked(document_id):
    b = await get_broker()
    return await b.is_document_locked(document_id)


async def push_task(task_id, priority="NORMAL"):
    b = await get_broker()
    await b.push_task(task_id, priority)


async def pop_task(timeout=5.0):
    b = await get_broker()
    return await b.pop_task(timeout)


async def task_done(task_id):
    b = await get_broker()
    await b.task_done(task_id)


async def queue_length():
    b = await get_broker()
    return await b.queue_length()


async def publish_sse_event(job_id, event, data):
    import json
    b = await get_broker()
    payload = json.dumps({"event": event, "data": data}, default=str)
    await b.publish(f"officeplane:sse:{job_id}", payload)


async def subscribe_sse_events(job_id):
    import json
    b = await get_broker()
    channel = f"officeplane:sse:{job_id}"
    async for ch, raw in b.subscribe(channel):
        if not raw:
            yield {"event": "_keepalive", "data": {}}
            continue
        payload = json.loads(raw)
        yield payload
        if payload.get("event") in ("stop", "error"):
            break
