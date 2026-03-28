"""
Redis broker — production backend.

Requires `redis[hiredis]` and a running Redis server.
Configure via REDIS_URL env var.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, AsyncGenerator, Dict, Optional

from officeplane.broker.base import Broker

log = logging.getLogger("officeplane.broker.redis")

LOCK_PREFIX = "officeplane:doclock:"
LOCK_TTL_SECONDS = 600
TASK_QUEUE_KEY = "officeplane:tasks"
TASK_PROCESSING_KEY = "officeplane:tasks:processing"


class RedisBroker(Broker):
    """Redis-backed broker for production multi-process deployments."""

    def __init__(self, url: Optional[str] = None):
        self._url = url or os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self._r = None

    # ── Lifecycle ────────────────────────────────────────────────────

    async def connect(self) -> None:
        import redis.asyncio as redis
        self._r = redis.from_url(self._url, decode_responses=True)
        await self._r.ping()
        log.info("RedisBroker connected: %s", self._url)

    async def close(self) -> None:
        if self._r:
            await self._r.aclose()
            self._r = None
            log.info("RedisBroker closed")

    def _redis(self):
        if self._r is None:
            raise RuntimeError("RedisBroker not connected — call connect() first")
        return self._r

    # ── Task dispatch ────────────────────────────────────────────────

    async def push_task(self, task_id: str, priority: str = "NORMAL") -> None:
        r = self._redis()
        payload = json.dumps({"task_id": task_id, "priority": priority})
        if priority in ("HIGH", "CRITICAL"):
            await r.lpush(TASK_QUEUE_KEY, payload)
        else:
            await r.rpush(TASK_QUEUE_KEY, payload)

    async def pop_task(self, timeout: float = 5.0) -> Optional[str]:
        r = self._redis()
        result = await r.blpop(TASK_QUEUE_KEY, timeout=int(timeout))
        if result is None:
            return None
        _, payload = result
        data = json.loads(payload)
        task_id = data["task_id"]
        await r.sadd(TASK_PROCESSING_KEY, task_id)
        return task_id

    async def task_done(self, task_id: str) -> None:
        r = self._redis()
        await r.srem(TASK_PROCESSING_KEY, task_id)

    async def queue_length(self) -> int:
        r = self._redis()
        return await r.llen(TASK_QUEUE_KEY)

    # ── Document locks ───────────────────────────────────────────────

    async def acquire_document_lock(
        self, document_id: str, holder: str, timeout: float = 30.0
    ) -> bool:
        r = self._redis()
        key = f"{LOCK_PREFIX}{document_id}"
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            acquired = await r.set(key, holder, nx=True, ex=LOCK_TTL_SECONDS)
            if acquired:
                return True
            await asyncio.sleep(0.5)

        return False

    async def release_document_lock(self, document_id: str, holder: str) -> bool:
        r = self._redis()
        key = f"{LOCK_PREFIX}{document_id}"
        lua = """
        if redis.call("get", KEYS[1]) == ARGV[1] then
            return redis.call("del", KEYS[1])
        else
            return 0
        end
        """
        result = await r.eval(lua, 1, key, holder)
        return result == 1

    async def is_document_locked(self, document_id: str) -> Optional[str]:
        r = self._redis()
        return await r.get(f"{LOCK_PREFIX}{document_id}")

    # ── Pub/Sub ──────────────────────────────────────────────────────

    async def publish(self, channel: str, data: str) -> None:
        r = self._redis()
        await r.publish(channel, data)

    async def subscribe(self, *channels: str) -> AsyncGenerator[tuple[str, str], None]:
        r = self._redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(*channels)
        try:
            while True:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=30.0
                )
                if msg is None:
                    yield ("", "")  # keepalive
                    continue
                if msg["type"] == "message":
                    yield (msg["channel"], msg["data"])
        finally:
            await pubsub.unsubscribe(*channels)
            await pubsub.aclose()

    # ── Key-Value ────────────────────────────────────────────────────

    async def hset(self, key: str, field: str, value: str) -> None:
        r = self._redis()
        await r.hset(key, field, value)

    async def hget(self, key: str, field: str) -> Optional[str]:
        r = self._redis()
        return await r.hget(key, field)

    async def hgetall(self, key: str) -> Dict[str, str]:
        r = self._redis()
        return await r.hgetall(key)

    async def rpush(self, key: str, value: str) -> None:
        r = self._redis()
        await r.rpush(key, value)

    async def lpop(self, key: str) -> Optional[str]:
        r = self._redis()
        return await r.lpop(key)

    async def sadd(self, key: str, member: str) -> None:
        r = self._redis()
        await r.sadd(key, member)

    async def sismember(self, key: str, member: str) -> bool:
        r = self._redis()
        return await r.sismember(key, member)

    async def delete(self, *keys: str) -> None:
        r = self._redis()
        await r.delete(*keys)
