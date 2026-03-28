"""
Teammate — an independent agent worker within a team.

Each teammate:
- Claims tasks from the shared task list
- Executes them using an LLM + tools
- Communicates with other teammates via mailbox
- Reports results back
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from officeplane.agent_team.mailbox import Mailbox, Message
from officeplane.agent_team.shared_tasks import SharedTaskList, TeamTask, TaskStatus

log = logging.getLogger("officeplane.agent_team.teammate")


class Teammate:
    """An independent agent worker within a team."""

    def __init__(
        self,
        teammate_id: str,
        team_id: str,
        role: str,
        system_prompt: str,
        task_list: SharedTaskList,
        model: str = "gpt-4o",
        tools: Optional[List[str]] = None,
    ):
        self.teammate_id = teammate_id
        self.team_id = team_id
        self.role = role
        self.system_prompt = system_prompt
        self.task_list = task_list
        self.model = model
        self.tools = tools or []
        self.mailbox = Mailbox(team_id, teammate_id)
        self._running = False
        self._conversation: List[Dict[str, str]] = []
        self._inbox: List[Message] = []

    async def run(self, on_event=None) -> Dict[str, Any]:
        """
        Main loop: claim tasks, execute them, repeat until done.

        on_event: optional async callback(teammate_id, event_type, data)
        """
        self._running = True
        completed = 0
        failed = 0

        # Start listening for messages in the background
        listener_task = asyncio.create_task(self._listen_loop())

        try:
            while self._running:
                # Claim next task
                task = await self.task_list.claim_task(self.teammate_id)

                if task is None:
                    # No tasks available — check if we're all done
                    if await self.task_list.is_all_done():
                        break
                    # Wait a bit, maybe a dependency will complete
                    await asyncio.sleep(1)
                    continue

                if on_event:
                    await on_event(self.teammate_id, "task_claimed", {
                        "task_id": task.id, "title": task.title
                    })

                # Execute the task
                try:
                    result = await self._execute_task(task)
                    await self.task_list.complete_task(task.id, result)
                    completed += 1

                    if on_event:
                        await on_event(self.teammate_id, "task_completed", {
                            "task_id": task.id, "result": result[:200]
                        })

                    # Notify the team
                    await self.mailbox.broadcast(
                        f"Completed task '{task.title}': {result[:200]}"
                    )

                except Exception as e:
                    error_msg = str(e)
                    await self.task_list.fail_task(task.id, error_msg)
                    failed += 1

                    if on_event:
                        await on_event(self.teammate_id, "task_failed", {
                            "task_id": task.id, "error": error_msg
                        })

                    await self.mailbox.broadcast(
                        f"Failed task '{task.title}': {error_msg}"
                    )

        finally:
            self._running = False
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

        return {
            "teammate_id": self.teammate_id,
            "role": self.role,
            "completed": completed,
            "failed": failed,
        }

    async def stop(self) -> None:
        """Signal this teammate to stop after current task."""
        self._running = False

    async def _execute_task(self, task: TeamTask) -> str:
        """Execute a task using the LLM."""
        # Include any messages from other teammates as context
        inbox_context = ""
        if self._inbox:
            msgs = self._inbox[-5:]  # Last 5 messages
            inbox_context = "\n\nRecent messages from teammates:\n"
            for m in msgs:
                inbox_context += f"- [{m.from_agent}]: {m.content}\n"
            self._inbox.clear()

        user_message = (
            f"Task: {task.title}\n\n"
            f"Description: {task.description}\n"
            f"{inbox_context}"
        )

        self._conversation.append({"role": "user", "content": user_message})

        client = AsyncOpenAI()
        response = await client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": self.system_prompt},
                *self._conversation,
            ],
            temperature=0.7,
            max_tokens=4096,
        )

        result = response.choices[0].message.content or ""
        self._conversation.append({"role": "assistant", "content": result})

        # Keep conversation manageable
        if len(self._conversation) > 20:
            self._conversation = self._conversation[-10:]

        return result

    async def _listen_loop(self) -> None:
        """Background loop: collect messages from other agents."""
        try:
            async for msg in self.mailbox.listen():
                if msg is None:
                    if not self._running:
                        break
                    continue
                self._inbox.append(msg)
                log.debug(
                    "[%s] Received from %s: %s",
                    self.teammate_id, msg.from_agent, msg.content[:80]
                )
        except asyncio.CancelledError:
            pass
