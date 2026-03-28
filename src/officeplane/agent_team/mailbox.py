"""
Mailbox — inter-agent messaging via the pluggable broker's pub/sub.

Each agent (lead or teammate) has a mailbox channel.
Agents can send direct messages or broadcast to the whole team.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Dict, Optional

log = logging.getLogger("officeplane.agent_team.mailbox")


@dataclass
class Message:
    from_agent: str
    to_agent: Optional[str]  # None = broadcast
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> Message:
        return cls(
            from_agent=data["from_agent"],
            to_agent=data.get("to_agent"),
            content=data["content"],
            timestamp=data.get("timestamp", 0),
            metadata=data.get("metadata", {}),
        )


class Mailbox:
    """Broker-backed mailbox for an agent within a team."""

    def __init__(self, team_id: str, agent_id: str):
        self.team_id = team_id
        self.agent_id = agent_id
        self._channel = f"officeplane:team:{team_id}:mail:{agent_id}"
        self._broadcast_channel = f"officeplane:team:{team_id}:broadcast"

    async def _broker(self):
        from officeplane.broker import get_broker
        return await get_broker()

    async def send(self, to_agent: str, content: str, **metadata) -> None:
        b = await self._broker()
        msg = Message(
            from_agent=self.agent_id,
            to_agent=to_agent,
            content=content,
            metadata=metadata,
        )
        target = f"officeplane:team:{self.team_id}:mail:{to_agent}"
        await b.publish(target, json.dumps(msg.to_dict()))
        log.debug("[%s -> %s] %s", self.agent_id, to_agent, content[:80])

    async def broadcast(self, content: str, **metadata) -> None:
        b = await self._broker()
        msg = Message(
            from_agent=self.agent_id,
            to_agent=None,
            content=content,
            metadata=metadata,
        )
        await b.publish(self._broadcast_channel, json.dumps(msg.to_dict()))
        log.debug("[%s -> ALL] %s", self.agent_id, content[:80])

    async def listen(self) -> AsyncGenerator[Optional[Message], None]:
        b = await self._broker()
        async for _channel, raw in b.subscribe(self._channel, self._broadcast_channel):
            if not raw:
                yield None  # keepalive
                continue
            data = json.loads(raw)
            if data.get("from_agent") == self.agent_id:
                continue
            yield Message.from_dict(data)
