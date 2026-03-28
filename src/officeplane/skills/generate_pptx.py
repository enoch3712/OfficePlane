"""
GeneratePPTXSkill — create a PPTX presentation with validation + quality check.

Driver: deepagents_cli (bypass permissions, setup script injects system prompt).
Validation: checks a .pptx file exists in the workspace after run.
Quality check: stub — override with a review agent pass.
"""

from __future__ import annotations

import logging
from pathlib import Path

from officeplane.skills.base import Skill, SkillContext, SkillResult

log = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).parent.parent / "content_agent" / "skills"


class GeneratePPTXSkill(Skill):
    name = "generate-pptx-quality"
    description = (
        "Generate a professional PPTX presentation with structure validation "
        "and automated quality review"
    )
    default_driver = "deepagents_cli"

    async def run(self, ctx: SkillContext) -> SkillResult:
        from officeplane.content_agent.drivers import get_driver
        from officeplane.content_agent.prompts import SYSTEM_PROMPT
        from officeplane.content_agent.storage import save_to_document_store
        from officeplane.content_agent.streaming import sse_manager

        system_prompt = SYSTEM_PROMPT + "\n\n" + self._load_skill_docs()
        message = self._build_message(ctx)
        driver = get_driver(ctx.driver)

        async for event in driver.astream(ctx.workspace, ctx.model, message, system_prompt):
            await sse_manager.push_event(ctx.job_id, event.type, event.data)

        document_id = await save_to_document_store(
            job_id=ctx.job_id,
            workspace=ctx.workspace,
            output_format="pptx",
            prompt=ctx.params.get("prompt", ""),
        )

        if not document_id:
            return SkillResult.failure("Failed to save generated PPTX to document store")

        return SkillResult.success(document_id=document_id, format="pptx")

    async def validate(self, ctx: SkillContext, result: SkillResult) -> list[str]:
        errors: list[str] = []
        pptx_files = list(ctx.workspace.rglob("*.pptx"))
        if not pptx_files:
            errors.append("No PPTX file was generated in the workspace")
        return errors

    async def quality_check(self, ctx: SkillContext, result: SkillResult) -> SkillResult:
        # TODO: spawn a review agent that checks slide count, content quality,
        # title presence, and consistency — then optionally regenerates weak slides.
        return result

    # ── Internal ──────────────────────────────────────────────────────────────

    def _build_message(self, ctx: SkillContext) -> str:
        parts = [ctx.params.get("prompt", "")]
        if slide_count := ctx.params.get("slide_count_hint"):
            parts.append(f"\nTarget slide count: {slide_count}")
        if style := ctx.params.get("style"):
            parts.append(f"\nStyle: {style}")
        if audience := ctx.params.get("audience"):
            parts.append(f"\nTarget audience: {audience}")
        parts.append("\nOutput format: PPTX (using pptxgenjs)")
        return "\n".join(parts)

    def _load_skill_docs(self) -> str:
        if not _SKILLS_DIR.exists():
            return ""
        parts: list[str] = []
        for f in sorted(_SKILLS_DIR.glob("*.md")):
            parts.append(f"\n## Skill: {f.stem}\n{f.read_text()}")
        return "\n".join(parts)
