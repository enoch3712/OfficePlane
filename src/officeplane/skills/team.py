"""
TeamSkill — orchestrate a multi-agent team for complex tasks.

Wraps the existing AgentTeam (lead + teammates with shared task list).
The team decomposes work, runs teammates in parallel, and synthesizes results.

Default teammates can be overridden via params["teammates"].
"""

from __future__ import annotations

import logging
from typing import Any

from officeplane.skills.base import Skill, SkillContext, SkillResult

log = logging.getLogger(__name__)

_DEFAULT_TEAMMATES: list[dict[str, str]] = [
    {
        "role": "researcher",
        "prompt": "Research the topic thoroughly and gather key facts, data, and context",
    },
    {
        "role": "writer",
        "prompt": "Write clear, engaging, well-structured content based on the research",
    },
    {
        "role": "reviewer",
        "prompt": "Review for quality, accuracy, consistency, and suggest improvements",
    },
]


class TeamSkill(Skill):
    name = "team"
    description = (
        "Orchestrate a team of specialized agents (researcher, writer, reviewer) "
        "to tackle complex multi-faceted tasks with parallel execution"
    )
    default_driver = "deepagents_sdk"

    async def run(self, ctx: SkillContext) -> SkillResult:
        from officeplane.agent_team.team import AgentTeam
        from officeplane.content_agent.streaming import sse_manager

        teammates: list[dict[str, Any]] = ctx.params.get("teammates", _DEFAULT_TEAMMATES)
        prompt = ctx.params.get("prompt", "")

        team = AgentTeam.create(
            prompt=prompt,
            teammates=teammates,
            model=ctx.model,
            document_id=ctx.params.get("document_id"),
        )

        async def _on_event(agent_id: str, event_type: str, data: dict) -> None:
            await sse_manager.push_event(
                ctx.job_id, event_type, {"agent_id": agent_id, **data}
            )

        team.on_event(_on_event)
        result = await team.run()

        if result["status"] == "failed":
            return SkillResult.failure(result.get("error", "Team execution failed"))

        return SkillResult.success(
            synthesis=result.get("synthesis", ""),
            task_summary=result.get("task_summary", {}),
            team_id=result.get("team_id", ""),
        )

    async def validate(self, ctx: SkillContext, result: SkillResult) -> list[str]:
        if not result.output.get("synthesis"):
            return ["Team produced no synthesis — all tasks may have failed"]
        return []
