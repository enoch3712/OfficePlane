"""
AgentTeam — orchestrates a team lead + teammates working on a shared task list.

Usage:
    team = AgentTeam.create(
        prompt="Create a pitch deck about AI in healthcare",
        teammates=[
            {"role": "researcher", "prompt": "Research the topic thoroughly"},
            {"role": "designer", "prompt": "Design the slide structure"},
            {"role": "writer", "prompt": "Write compelling content"},
        ],
    )
    result = await team.run()
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Coroutine, Dict, List, Optional
from uuid import uuid4

from openai import AsyncOpenAI

from officeplane.agent_team.mailbox import Mailbox
from officeplane.agent_team.shared_tasks import SharedTaskList, TeamTask, TaskStatus
from officeplane.agent_team.teammate import Teammate

log = logging.getLogger("officeplane.agent_team.team")

LEAD_SYSTEM_PROMPT = """You are a team lead coordinating a group of AI teammates.
Your job is to:
1. Break down the user's request into concrete, independent tasks
2. Assign tasks considering dependencies (some tasks must complete before others)
3. After all tasks complete, synthesize the results into a final deliverable

Respond with a JSON object:
{
  "tasks": [
    {
      "id": "task_1",
      "title": "Short task title",
      "description": "Detailed description of what to do",
      "depends_on": []
    },
    {
      "id": "task_2",
      "title": "Another task",
      "description": "This depends on task_1 results",
      "depends_on": ["task_1"]
    }
  ]
}

Keep tasks focused and independent where possible so teammates can work in parallel.
Create 3-6 tasks per teammate for good utilization.
"""

SYNTHESIS_PROMPT = """You are synthesizing results from multiple teammates.
Combine their outputs into a single coherent result.
Resolve any conflicts between their findings.
Be concise but complete."""


class AgentTeam:
    """Coordinates a team of AI agents working on a shared task list."""

    def __init__(
        self,
        team_id: str,
        prompt: str,
        teammate_configs: List[Dict[str, str]],
        model: str = "gpt-4o",
        document_id: Optional[str] = None,
    ):
        self.team_id = team_id
        self.prompt = prompt
        self.model = model
        self.document_id = document_id
        self.task_list = SharedTaskList(team_id)
        self.lead_mailbox = Mailbox(team_id, "lead")
        self._teammate_configs = teammate_configs
        self._teammates: List[Teammate] = []
        self._on_event: Optional[Callable] = None

    @classmethod
    def create(
        cls,
        prompt: str,
        teammates: List[Dict[str, str]],
        model: str = "gpt-4o",
        document_id: Optional[str] = None,
    ) -> AgentTeam:
        """Create a new agent team."""
        team_id = f"team_{uuid4().hex[:12]}"
        return cls(
            team_id=team_id,
            prompt=prompt,
            teammate_configs=teammates,
            model=model,
            document_id=document_id,
        )

    def on_event(self, callback: Callable) -> None:
        """Set event callback: async fn(agent_id, event_type, data)."""
        self._on_event = callback

    async def run(self) -> Dict[str, Any]:
        """
        Full team execution:
        1. Lead decomposes work into tasks
        2. Teammates run in parallel, claiming and completing tasks
        3. Lead synthesizes results
        """
        start_time = time.time()

        await self._emit("lead", "team_started", {
            "team_id": self.team_id,
            "teammates": len(self._teammate_configs),
        })

        try:
            # Step 1: Lead decomposes work
            await self._emit("lead", "decomposing", {"prompt": self.prompt[:200]})
            tasks = await self._decompose_work()
            await self.task_list.add_tasks(tasks)

            await self._emit("lead", "tasks_created", {
                "count": len(tasks),
                "tasks": [{"id": t.id, "title": t.title} for t in tasks],
            })

            # Step 2: Spawn teammates and run in parallel
            self._teammates = self._spawn_teammates()
            teammate_tasks = [
                asyncio.create_task(t.run(on_event=self._on_event))
                for t in self._teammates
            ]

            await self._emit("lead", "teammates_started", {
                "teammates": [
                    {"id": t.teammate_id, "role": t.role}
                    for t in self._teammates
                ],
            })

            # Wait for all teammates to finish
            results = await asyncio.gather(*teammate_tasks, return_exceptions=True)

            # Step 3: Synthesize results
            await self._emit("lead", "synthesizing", {})
            all_tasks = await self.task_list.get_all_tasks()
            synthesis = await self._synthesize(all_tasks)

            duration_ms = int((time.time() - start_time) * 1000)
            summary = await self.task_list.summary()

            await self._emit("lead", "team_completed", {
                "duration_ms": duration_ms,
                "summary": summary,
            })

            return {
                "team_id": self.team_id,
                "status": "completed",
                "duration_ms": duration_ms,
                "task_summary": summary,
                "teammate_results": [
                    r if isinstance(r, dict) else {"error": str(r)}
                    for r in results
                ],
                "synthesis": synthesis,
            }

        except Exception as e:
            log.error("Team %s failed: %s", self.team_id, e, exc_info=True)
            await self._emit("lead", "team_failed", {"error": str(e)})
            return {
                "team_id": self.team_id,
                "status": "failed",
                "error": str(e),
                "duration_ms": int((time.time() - start_time) * 1000),
            }
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        """Stop all teammates and clean up Redis state."""
        for t in self._teammates:
            await t.stop()
        await self.task_list.cleanup()

    # ── Internal ──────────────────────────────────────────────────────

    async def _decompose_work(self) -> List[TeamTask]:
        """Use the lead LLM to break the prompt into tasks."""
        client = AsyncOpenAI()

        teammate_desc = "\n".join(
            f"- {c['role']}: {c.get('prompt', c['role'])}"
            for c in self._teammate_configs
        )

        response = await client.chat.completions.create(
            model=self.model,
            temperature=0.7,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": LEAD_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Request: {self.prompt}\n\n"
                        f"Available teammates:\n{teammate_desc}\n\n"
                        f"Break this into tasks. Return JSON only."
                    ),
                },
            ],
            response_format={"type": "json_object"},
        )

        raw = response.choices[0].message.content or "{}"
        data = json.loads(raw)
        tasks_data = data.get("tasks", [])

        return [
            TeamTask(
                id=t.get("id", f"task_{i}"),
                title=t["title"],
                description=t["description"],
                depends_on=t.get("depends_on", []),
            )
            for i, t in enumerate(tasks_data)
        ]

    def _spawn_teammates(self) -> List[Teammate]:
        """Create Teammate instances from configs."""
        teammates = []
        for i, config in enumerate(self._teammate_configs):
            role = config["role"]
            tm = Teammate(
                teammate_id=f"{role}_{i}",
                team_id=self.team_id,
                role=role,
                system_prompt=config.get("prompt", f"You are a {role}."),
                task_list=self.task_list,
                model=self.model,
            )
            teammates.append(tm)
        return teammates

    async def _synthesize(self, tasks: List[TeamTask]) -> str:
        """Lead synthesizes all completed task results."""
        completed = [t for t in tasks if t.status == TaskStatus.COMPLETED]
        if not completed:
            return "No tasks completed successfully."

        results_text = "\n\n".join(
            f"### {t.title}\n{t.result}" for t in completed
        )

        client = AsyncOpenAI()
        response = await client.chat.completions.create(
            model=self.model,
            temperature=0.5,
            max_tokens=4096,
            messages=[
                {"role": "system", "content": SYNTHESIS_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Original request: {self.prompt}\n\n"
                        f"Teammate results:\n{results_text}\n\n"
                        f"Synthesize these into a final, coherent result."
                    ),
                },
            ],
        )
        return response.choices[0].message.content or ""

    async def _emit(self, agent_id: str, event_type: str, data: dict) -> None:
        """Emit an event and publish to SSE."""
        if self._on_event:
            await self._on_event(agent_id, event_type, data)
        # Also publish to Redis SSE channel for the team
        try:
            from officeplane.management.redis_client import publish_sse_event
            await publish_sse_event(self.team_id, event_type, {
                "agent_id": agent_id,
                **data,
            })
        except Exception:
            pass
