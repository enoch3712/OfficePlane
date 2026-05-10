"""Content agent runner - orchestrates DeepAgents for content generation."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path
from typing import Any, Dict, Optional

from officeplane.content_agent.config import ContentAgentConfig
from officeplane.content_agent.models import JobState, OutputFormat
from officeplane.content_agent.prompts import SYSTEM_PROMPT
from officeplane.content_agent.streaming import sse_manager
from officeplane.content_agent.storage import save_to_document_store
from officeplane.content_agent.workspace import WorkspaceManager

log = logging.getLogger("officeplane.content_agent.runner")


class ContentAgentRunner:
    """Runs the content generation agent for a single job."""

    def __init__(self, config: Optional[ContentAgentConfig] = None):
        self.config = config or ContentAgentConfig.from_env()
        self.workspace_mgr = WorkspaceManager(self.config.workspace_root)

    async def run(
        self,
        job_id: str,
        prompt: str,
        output_format: OutputFormat = OutputFormat.PPTX,
        model_override: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
        driver: str = "deepagents_sdk",
    ) -> Dict[str, Any]:
        """
        Execute the content generation agent.

        Returns a dict with job result including document_id.
        """
        start_time = time.time()
        workspace = self.workspace_mgr.create(job_id)
        model = model_override or self.config.model
        options = options or {}

        await sse_manager.push_event(job_id, "start", {"job_id": job_id})

        try:
            # Build the user message with format instructions
            user_message = self._build_user_message(prompt, output_format, options)

            await sse_manager.push_event(
                job_id, "delta", {"text": "Initializing agent..."}
            )

            # Run the agent
            await self._run_agent(job_id, workspace, model, user_message, driver)

            await sse_manager.push_event(
                job_id, "delta", {"text": "Saving results to document store..."}
            )

            # Save to document store
            document_id = await save_to_document_store(
                job_id=job_id,
                workspace=workspace,
                output_format=output_format.value,
                prompt=prompt,
            )

            duration_ms = int((time.time() - start_time) * 1000)

            await sse_manager.push_event(
                job_id,
                "stop",
                {
                    "duration_ms": duration_ms,
                    "document_id": document_id,
                    "status": "completed",
                },
            )

            return {
                "status": "completed",
                "document_id": document_id,
                "duration_ms": duration_ms,
            }

        except Exception as e:
            log.error("Job %s failed: %s", job_id, e, exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)

            await sse_manager.push_event(
                job_id,
                "stop",
                {
                    "duration_ms": duration_ms,
                    "status": "failed",
                    "error": str(e),
                },
            )

            return {
                "status": "failed",
                "error": str(e),
                "duration_ms": duration_ms,
            }

    async def _run_agent(
        self,
        job_id: str,
        workspace: Path,
        model: str,
        user_message: str,
        driver: str = "deepagents_sdk",
    ) -> None:
        """Run the agent via the selected driver with streaming events."""
        from officeplane.content_agent.drivers import get_driver

        skills = self._load_skills()
        system_prompt = SYSTEM_PROMPT + "\n\n" + skills

        try:
            agent_driver = get_driver(driver)
            async for event in agent_driver.astream(workspace, model, user_message, system_prompt):
                await self._handle_agent_event(job_id, event)
        except ImportError:
            if driver == "deepagents_sdk":
                log.warning("deepagents not installed, falling back to direct LLM generation")
                await self._fallback_generate(job_id, workspace, model, user_message)
            else:
                raise

    async def _fallback_generate(
        self,
        job_id: str,
        workspace: Path,
        model: str,
        user_message: str,
    ) -> None:
        """Fallback: call the LLM through LiteLLM to produce a pptxgenjs script."""
        import litellm

        await sse_manager.push_event(
            job_id, "delta", {"text": "Planning presentation structure..."}
        )

        response = await litellm.acompletion(
            model=model,
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
                {
                    "role": "user",
                    "content": (
                        "Write a complete Node.js script using pptxgenjs that creates this "
                        "presentation. The script should:\n"
                        "1. Create the PPTX file as 'presentation.pptx' in the current directory\n"
                        "2. Write a 'metadata.json' with {title, slides: [{title, description}]}\n"
                        "3. Use professional styling and colors\n\n"
                        "Output ONLY the Node.js code, no explanation. Start with requires."
                    ),
                },
            ],
        )

        script_content = response.choices[0].message.content
        # Strip markdown code fences if present
        if script_content.startswith("```"):
            lines = script_content.split("\n")
            script_content = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])

        script_path = workspace / "create-presentation.js"
        script_path.write_text(script_content)

        await sse_manager.push_event(
            job_id, "tool_call", {"name": "bash", "arguments": {"command": "node create-presentation.js"}}
        )

        # Execute the script
        proc = await asyncio.create_subprocess_exec(
            "node",
            str(script_path),
            cwd=str(workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=self.config.job_timeout_seconds
        )

        result_text = stdout.decode() if stdout else ""
        error_text = stderr.decode() if stderr else ""

        await sse_manager.push_event(
            job_id,
            "tool_result",
            {
                "name": "bash",
                "result": result_text or "Script completed",
                "is_error": proc.returncode != 0,
            },
        )

        if proc.returncode != 0:
            raise RuntimeError(f"Presentation generation failed: {error_text}")

    async def _handle_agent_event(self, job_id: str, event: Any) -> None:
        """Forward a normalized AgentEvent to the SSE stream."""
        from officeplane.content_agent.drivers import AgentEvent

        if not isinstance(event, AgentEvent):
            return

        if event.type == "delta":
            text = event.data.get("text", "")
            if text:
                await sse_manager.push_event(job_id, "delta", {"text": text})
        elif event.type == "tool_call":
            await sse_manager.push_event(job_id, "tool_call", event.data)
        elif event.type == "tool_result":
            await sse_manager.push_event(job_id, "tool_result", event.data)

    def _build_user_message(
        self,
        prompt: str,
        output_format: OutputFormat,
        options: Dict[str, Any],
    ) -> str:
        """Build the user message for the agent."""
        parts = [prompt]

        if output_format == OutputFormat.HTML:
            parts.append("\nOutput format: HTML (reveal.js or standalone HTML)")
        elif output_format == OutputFormat.BOTH:
            parts.append("\nOutput formats: PPTX and HTML")
        else:
            parts.append("\nOutput format: PPTX (using pptxgenjs)")

        if slide_count := options.get("slide_count_hint"):
            parts.append(f"\nTarget slide count: {slide_count}")

        if style := options.get("style"):
            parts.append(f"\nStyle: {style}")

        if audience := options.get("audience"):
            parts.append(f"\nTarget audience: {audience}")

        return "\n".join(parts)

    def _load_skills(self) -> str:
        """Load skill files from the skills directory."""
        skills_dir = Path(__file__).parent / "skills"
        if not skills_dir.exists():
            return ""

        parts = []
        for skill_file in sorted(skills_dir.glob("*.md")):
            parts.append(f"\n## Skill: {skill_file.stem}\n")
            parts.append(skill_file.read_text())

        return "\n".join(parts) if parts else ""
