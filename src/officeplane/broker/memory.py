"""
In-memory broker — zero external dependencies.

Good for development, testing, or single-process deployments.
All state lives in-process and is lost on restart.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict
from typing import Any, AsyncGenerator, Dict, Optional

from officeplane.broker.base import Broker

log = logging.getLogger("officeplane.broker.memory")


class MemoryBroker(Broker):
    """Pure-Python in-process broker backed by asyncio primitives."""

    def __init__(self):
        # Task dispatch
        self._task_queue: asyncio.Queue[str] = asyncio.Queue()
        self._processing: set[str] = set()

        # Document locks: doc_id → holder
        self._locks: dict[str, str] = {}
        self._lock_events: dict[str, asyncio.Event] = defaultdict(asyncio.Event)

        # Pub/Sub: channel → list of asyncio.Queue
        self._subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)

        # Key-value stores
        self._hashes: dict[str, dict[str, str]] = defaultdict(dict)
        self._lists: dict[str, list[str]] = defaultdict(list)
        self._sets: dict[str, set[str]] = defaultdict(set)

    # ── Lifecycle ────────────────────────────────────────────────────

    async def connect(self) -> None:
        log.info("MemoryBroker connected (in-process)")

    async def close(self) -> None:
        self._task_queue = asyncio.Queue()
        self._processing.clear()
        self._locks.clear()
        self._subscribers.clear()
        self._hashes.clear()
        self._lists.clear()
        self._sets.clear()
        log.info("MemoryBroker closed")

    # ── Task dispatch ────────────────────────────────────────────────

    async def push_task(self, task_id: str, priority: str = "NORMAL") -> None:
        await self._task_queue.put(json.dumps({"task_id": task_id, "priority": priority}))

    async def pop_task(self, timeout: float = 5.0) -> Optional[str]:
        try:
            raw = await asyncio.wait_for(self._task_queue.get(), timeout=timeout)
            data = json.loads(raw)
            task_id = data["task_id"]
            self._processing.add(task_id)
            return task_id
        except asyncio.TimeoutError:
            return None

    async def task_done(self, task_id: str) -> None:
        self._processing.discard(task_id)

    async def queue_length(self) -> int:
        return self._task_queue.qsize()

    # ── Document locks ───────────────────────────────────────────────

    async def acquire_document_lock(
        self, document_id: str, holder: str, timeout: float = 30.0
    ) -> bool:
        deadline = asyncio.get_event_loop().time() + timeout

        while asyncio.get_event_loop().time() < deadline:
            if document_id not in self._locks:
                self._locks[document_id] = holder
                return True
            await asyncio.sleep(0.2)

        return False

    async def release_document_lock(self, document_id: str, holder: str) -> bool:
        if self._locks.get(document_id) == holder:
            del self._locks[document_id]
            return True
        return False

    async def is_document_locked(self, document_id: str) -> Optional[str]:
        return self._locks.get(document_id)

    # ── Pub/Sub ──────────────────────────────────────────────────────

    async def publish(self, channel: str, data: str) -> None:
        for q in self._subscribers.get(channel, []):
            await q.put((channel, data))

    async def subscribe(self, *channels: str) -> AsyncGenerator[tuple[str, str], None]:
        q: asyncio.Queue[tuple[str, str]] = asyncio.Queue()
        for ch in channels:
            self._subscribers[ch].append(q)
        try:
            while True:
                try:
                    item = await asyncio.wait_for(q.get(), timeout=30.0)
                    yield item
                except asyncio.TimeoutError:
                    yield ("", "")  # keepalive
        finally:
            for ch in channels:
                try:
                    self._subscribers[ch].remove(q)
                except ValueError:
                    pass

    # ── Key-Value ────────────────────────────────────────────────────

    async def hset(self, key: str, field: str, value: str) -> None:
        self._hashes[key][field] = value

    async def hget(self, key: str, field: str) -> Optional[str]:
        return self._hashes.get(key, {}).get(field)

    async def hgetall(self, key: str) -> Dict[str, str]:
        return dict(self._hashes.get(key, {}))

    async def rpush(self, key: str, value: str) -> None:
        self._lists[key].append(value)

    async def lpop(self, key: str) -> Optional[str]:
        lst = self._lists.get(key, [])
        if lst:
            return lst.pop(0)
        return None

    async def sadd(self, key: str, member: str) -> None:
        self._sets[key].add(member)

    async def sismember(self, key: str, member: str) -> bool:
        return member in self._sets.get(key, set())

    async def delete(self, *keys: str) -> None:
        for k in keys:
            self._hashes.pop(k, None)
            self._lists.pop(k, None)
            self._sets.pop(k, None)
