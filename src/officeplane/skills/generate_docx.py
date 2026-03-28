"""
GenerateDOCXSkill — create a styled Word document with proper heading hierarchy.

Driver: deepagents_cli (bypass permissions).
The agent writes python-docx code to generate a .docx with consistent styles.
Validation: checks a .docx file exists in the workspace after run.
Quality check: stub — override to review style consistency and structure.
"""

from __future__ import annotations

import logging

from officeplane.skills.base import Skill, SkillContext, SkillResult

log = logging.getLogger(__name__)

_SYSTEM_PROMPT = """You are an expert document author specializing in professional Word documents.

## Available Tools
- **Python 3** with `python-docx` installed
- **LibreOffice** for format conversion if needed

## Your Process
1. Analyze the request to understand content, audience, and document type
2. Plan the document structure with clear section hierarchy
3. Write a Python script using python-docx to generate the document
4. Execute the script to produce the .docx file
5. Write a metadata.json with {title, sections: [{heading, summary}]}

## Output Requirements
- Save the primary output as `document.docx` in the current directory
- Always write `metadata.json` alongside the document

## Style Standards
- Apply heading hierarchy: Heading 1 for major sections, Heading 2 for subsections
- Use Normal style for body paragraphs with consistent spacing (12pt after)
- Title page with document title, author, and date when appropriate
- Table of contents for documents longer than 5 sections
- Consistent font: Calibri 11pt for body, matching heading sizes
- Professional formatting: 2.5cm margins, justified body text

## IMPORTANT
- Work entirely within the workspace directory
- Write all code to files before executing
- If python-docx fails, try an alternative approach
"""


class GenerateDOCXSkill(Skill):
    name = "generate-docx-styled"
    description = (
        "Generate a styled Word document with proper heading hierarchy, "
        "consistent formatting, and optional table of contents"
    )
    default_driver = "deepagents_cli"

    async def run(self, ctx: SkillContext) -> SkillResult:
        from officeplane.content_agent.drivers import get_driver
        from officeplane.content_agent.storage import save_to_document_store
        from officeplane.content_agent.streaming import sse_manager

        message = self._build_message(ctx)
        driver = get_driver(ctx.driver)

        async for event in driver.astream(ctx.workspace, ctx.model, message, _SYSTEM_PROMPT):
            await sse_manager.push_event(ctx.job_id, event.type, event.data)

        document_id = await save_to_document_store(
            job_id=ctx.job_id,
            workspace=ctx.workspace,
            output_format="docx",
            prompt=ctx.params.get("prompt", ""),
        )

        if not document_id:
            return SkillResult.failure("Failed to save generated DOCX to document store")

        return SkillResult.success(document_id=document_id, format="docx")

    async def validate(self, ctx: SkillContext, result: SkillResult) -> list[str]:
        errors: list[str] = []
        docx_files = list(ctx.workspace.rglob("*.docx"))
        if not docx_files:
            errors.append("No DOCX file was generated in the workspace")
        return errors

    async def quality_check(self, ctx: SkillContext, result: SkillResult) -> SkillResult:
        # TODO: review heading structure, style consistency, section completeness
        return result

    def _build_message(self, ctx: SkillContext) -> str:
        parts = [ctx.params.get("prompt", "")]
        if doc_type := ctx.params.get("document_type"):
            parts.append(f"\nDocument type: {doc_type}")
        if style_guide := ctx.params.get("style_guide"):
            parts.append(f"\nStyle guide: {style_guide}")
        if sections := ctx.params.get("sections"):
            parts.append(f"\nRequired sections: {', '.join(sections)}")
        parts.append("\nOutput format: DOCX (using python-docx)")
        return "\n".join(parts)
