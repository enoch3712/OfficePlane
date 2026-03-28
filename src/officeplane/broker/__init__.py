"""
Pluggable broker for queue dispatch, document locks, pub/sub, and KV.

Configure via environment variable:

    OFFICEPLANE_BROKER=memory   # In-process, zero deps (default)
    OFFICEPLANE_BROKER=redis    # Requires Redis server + redis[hiredis]

The singleton is created on first call to get_broker().
"""

from __future__ import annotations

import logging
import os
from typing import Optional

from officeplane.broker.base import Broker

log = logging.getLogger("officeplane.broker")

_broker: Optional[Broker] = None


def _create_broker() -> Broker:
    """Instantiate the broker based on OFFICEPLANE_BROKER env var."""
    backend = os.getenv("OFFICEPLANE_BROKER", "memory").lower()

    if backend == "redis":
        from officeplane.broker.redis_backend import RedisBroker
        return RedisBroker()
    elif backend == "memory":
        from officeplane.broker.memory import MemoryBroker
        return MemoryBroker()
    else:
        raise ValueError(
            f"Unknown broker backend: {backend!r}. "
            f"Supported: 'memory', 'redis'"
        )


async def get_broker() -> Broker:
    """Get or create the global broker singleton."""
    global _broker
    if _broker is None:
        _broker = _create_broker()
        await _broker.connect()
    return _broker


async def close_broker() -> None:
    """Shut down the global broker."""
    global _broker
    if _broker is not None:
        await _broker.close()
        _broker = None
