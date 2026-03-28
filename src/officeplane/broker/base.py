"""
Abstract broker interface.

Every backend (memory, redis, etc.) implements this protocol.
Consumers import `get_broker()` and never know which backend is active.
"""

from __future__ import annotations

import abc
from typing import Any, AsyncGenerator, Dict, Optional


class Broker(abc.ABC):
    """
    Unified interface for queue dispatch, document locks, pub/sub, and
    key-value operations.  Configured once at startup via OFFICEPLANE_BROKER.
    """

    # ── Lifecycle ────────────────────────────────────────────────────

    @abc.abstractmethod
    async def connect(self) -> None: ...

    @abc.abstractmethod
    async def close(self) -> None: ...

    # ── Task dispatch ────────────────────────────────────────────────

    @abc.abstractmethod
    async def push_task(self, task_id: str, priority: str = "NORMAL") -> None: ...

    @abc.abstractmethod
    async def pop_task(self, timeout: float = 5.0) -> Optional[str]: ...

    @abc.abstractmethod
    async def task_done(self, task_id: str) -> None: ...

    @abc.abstractmethod
    async def queue_length(self) -> int: ...

    # ── Document locks ───────────────────────────────────────────────

    @abc.abstractmethod
    async def acquire_document_lock(
        self, document_id: str, holder: str, timeout: float = 30.0
    ) -> bool: ...

    @abc.abstractmethod
    async def release_document_lock(
        self, document_id: str, holder: str
    ) -> bool: ...

    @abc.abstractmethod
    async def is_document_locked(self, document_id: str) -> Optional[str]: ...

    # ── Pub/Sub ──────────────────────────────────────────────────────

    @abc.abstractmethod
    async def publish(self, channel: str, data: str) -> None: ...

    @abc.abstractmethod
    async def subscribe(self, *channels: str) -> AsyncGenerator[tuple[str, str], None]:
        """Yield (channel, data_json) tuples. Yields (channel, "") on timeout as keepalive."""
        ...

    # ── Key-Value (hash, list, set) ──────────────────────────────────
    # Used by SharedTaskList and Mailbox.

    @abc.abstractmethod
    async def hset(self, key: str, field: str, value: str) -> None: ...

    @abc.abstractmethod
    async def hget(self, key: str, field: str) -> Optional[str]: ...

    @abc.abstractmethod
    async def hgetall(self, key: str) -> Dict[str, str]: ...

    @abc.abstractmethod
    async def rpush(self, key: str, value: str) -> None: ...

    @abc.abstractmethod
    async def lpop(self, key: str) -> Optional[str]: ...

    @abc.abstractmethod
    async def sadd(self, key: str, member: str) -> None: ...

    @abc.abstractmethod
    async def sismember(self, key: str, member: str) -> bool: ...

    @abc.abstractmethod
    async def delete(self, *keys: str) -> None: ...
