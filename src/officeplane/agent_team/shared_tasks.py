"""
Shared task list for agent teams.

Backed by the pluggable broker (memory or redis).
Teammates claim tasks atomically (no double-claiming).
Tasks can have dependencies — a task is only claimable when all its
dependencies are completed.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

log = logging.getLogger("officeplane.agent_team.shared_tasks")


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class TeamTask:
    id: str
    title: str
    description: str
    status: TaskStatus = TaskStatus.PENDING
    assigned_to: Optional[str] = None
    depends_on: List[str] = field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "status": self.status.value,
            "assigned_to": self.assigned_to,
            "depends_on": self.depends_on,
            "result": self.result,
            "error": self.error,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> TeamTask:
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            status=TaskStatus(data["status"]),
            assigned_to=data.get("assigned_to"),
            depends_on=data.get("depends_on", []),
            result=data.get("result"),
            error=data.get("error"),
            metadata=data.get("metadata", {}),
        )


class SharedTaskList:
    """Broker-backed shared task list for an agent team."""

    def __init__(self, team_id: str):
        self.team_id = team_id
        self._tasks_key = f"officeplane:team:{team_id}:tasks"
        self._available_key = f"officeplane:team:{team_id}:available"
        self._completed_key = f"officeplane:team:{team_id}:completed"

    async def _broker(self):
        from officeplane.broker import get_broker
        return await get_broker()

    async def add_task(self, task: TeamTask) -> None:
        b = await self._broker()
        await b.hset(self._tasks_key, task.id, json.dumps(task.to_dict()))
        if await self._deps_met(task.depends_on):
            await b.rpush(self._available_key, task.id)
        log.info("[Team %s] Task added: %s", self.team_id, task.id)

    async def add_tasks(self, tasks: List[TeamTask]) -> None:
        for task in tasks:
            await self.add_task(task)

    async def claim_task(self, teammate_id: str) -> Optional[TeamTask]:
        b = await self._broker()

        while True:
            task_id = await b.lpop(self._available_key)
            if task_id is None:
                return None

            raw = await b.hget(self._tasks_key, task_id)
            if raw is None:
                continue

            task = TeamTask.from_dict(json.loads(raw))

            if task.status != TaskStatus.PENDING:
                continue

            if not await self._deps_met(task.depends_on):
                await b.rpush(self._available_key, task_id)
                continue

            task.status = TaskStatus.IN_PROGRESS
            task.assigned_to = teammate_id
            await b.hset(self._tasks_key, task.id, json.dumps(task.to_dict()))
            log.info("[Team %s] Task %s claimed by %s", self.team_id, task.id, teammate_id)
            return task

    async def complete_task(self, task_id: str, result: str) -> None:
        b = await self._broker()
        raw = await b.hget(self._tasks_key, task_id)
        if raw is None:
            return
        task = TeamTask.from_dict(json.loads(raw))
        task.status = TaskStatus.COMPLETED
        task.result = result
        await b.hset(self._tasks_key, task.id, json.dumps(task.to_dict()))
        await b.sadd(self._completed_key, task_id)
        log.info("[Team %s] Task %s completed", self.team_id, task_id)
        await self._unblock_dependents(task_id)

    async def fail_task(self, task_id: str, error: str) -> None:
        b = await self._broker()
        raw = await b.hget(self._tasks_key, task_id)
        if raw is None:
            return
        task = TeamTask.from_dict(json.loads(raw))
        task.status = TaskStatus.FAILED
        task.error = error
        await b.hset(self._tasks_key, task.id, json.dumps(task.to_dict()))
        log.info("[Team %s] Task %s failed: %s", self.team_id, task_id, error)

    async def get_all_tasks(self) -> List[TeamTask]:
        b = await self._broker()
        raw_tasks = await b.hgetall(self._tasks_key)
        return [TeamTask.from_dict(json.loads(v)) for v in raw_tasks.values()]

    async def get_task(self, task_id: str) -> Optional[TeamTask]:
        b = await self._broker()
        raw = await b.hget(self._tasks_key, task_id)
        if raw is None:
            return None
        return TeamTask.from_dict(json.loads(raw))

    async def is_all_done(self) -> bool:
        tasks = await self.get_all_tasks()
        return all(t.status in (TaskStatus.COMPLETED, TaskStatus.FAILED) for t in tasks)

    async def summary(self) -> Dict[str, int]:
        tasks = await self.get_all_tasks()
        counts: Dict[str, int] = {}
        for t in tasks:
            counts[t.status.value] = counts.get(t.status.value, 0) + 1
        return counts

    async def cleanup(self) -> None:
        b = await self._broker()
        await b.delete(self._tasks_key, self._available_key, self._completed_key)

    async def _deps_met(self, depends_on: List[str]) -> bool:
        if not depends_on:
            return True
        b = await self._broker()
        for dep_id in depends_on:
            if not await b.sismember(self._completed_key, dep_id):
                return False
        return True

    async def _unblock_dependents(self, completed_task_id: str) -> None:
        b = await self._broker()
        all_raw = await b.hgetall(self._tasks_key)
        for raw in all_raw.values():
            task = TeamTask.from_dict(json.loads(raw))
            if task.status != TaskStatus.PENDING:
                continue
            if completed_task_id not in task.depends_on:
                continue
            if await self._deps_met(task.depends_on):
                await b.rpush(self._available_key, task.id)
                log.info("[Team %s] Task %s unblocked", self.team_id, task.id)
