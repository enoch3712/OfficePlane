"""
Agent driver abstractions for content generation.

Drivers encapsulate how the agent is invoked — SDK or CLI — so the
runner stays agnostic. Each driver yields normalized AgentEvents.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, AsyncIterator, Optional

log = logging.getLogger(__name__)


@dataclass
class AgentEvent:
    """Normalized event emitted by any driver."""
    type: str  # "delta" | "tool_call" | "tool_result"
    data: dict


class DeepAgentsSDKDriver:
    """Invoke deepagents via the Python SDK (current approach).

    The model string is provider-prefixed (LiteLLM convention, e.g.
    ``deepseek/deepseek-chat``). We build a ``ChatLiteLLM`` instance and pass
    it to deepagents so the same factory handles every provider.
    """

    async def astream(
        self, workspace: Path, model: str, message: str, system_prompt: str
    ) -> AsyncIterator[AgentEvent]:
        from deepagents import create_deep_agent
        from deepagents.backends import LocalShellBackend

        from officeplane.content_agent.model import ModelConfig, build_chat_model

        chat_model = build_chat_model(ModelConfig(model=model))
        backend = LocalShellBackend(root_dir=str(workspace))
        agent = create_deep_agent(
            model=chat_model, system_prompt=system_prompt, backend=backend
        )

        async for raw in agent.astream(message):
            event = _normalize_sdk_event(raw)
            if event:
                yield event


class DeepAgentsCLIDriver:
    """
    Invoke the DeepAgents CLI as a subprocess with bypass permissions.

    The setup script is written to the workspace and passed via --setup-script
    so the CLI agent inherits the system prompt and skills without prompting.
    """

    def __init__(
        self,
        bypass_permissions: bool = True,
        setup_script: Optional[str] = None,
        cli_command: str = "deepagents",
    ):
        self.bypass_permissions = bypass_permissions
        self.setup_script = setup_script
        self.cli_command = cli_command

    async def astream(
        self, workspace: Path, model: str, message: str, system_prompt: str
    ) -> AsyncIterator[AgentEvent]:
        setup_path = self._write_setup_script(workspace, system_prompt)
        script = self.setup_script or str(setup_path)

        cmd = [self.cli_command]
        if self.bypass_permissions:
            cmd.append("--yes")
        cmd.extend(["--model", model, "--setup-script", script, message])

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=str(workspace),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Drain stderr in background to prevent pipe deadlock
        stderr_chunks: list[str] = []

        async def _drain_stderr() -> None:
            assert proc.stderr
            async for line in proc.stderr:
                stderr_chunks.append(line.decode())

        stderr_task = asyncio.create_task(_drain_stderr())

        assert proc.stdout
        async for line in proc.stdout:
            text = line.decode().rstrip()
            if text:
                yield AgentEvent(type="delta", data={"text": text + "\n"})

        await proc.wait()
        await stderr_task

        if proc.returncode != 0:
            stderr_text = "".join(stderr_chunks)[:500]
            raise RuntimeError(
                f"deepagents CLI exited {proc.returncode}: {stderr_text}"
            )

    def _write_setup_script(self, workspace: Path, system_prompt: str) -> Path:
        """Write a Python setup script to the workspace that configures the system prompt."""
        script_path = workspace / "da_setup.py"
        escaped = system_prompt.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')
        script_path.write_text(
            f'from deepagents.cli import configure\n\n'
            f'configure(\n    system_prompt="""{escaped}""",\n)\n'
        )
        return script_path


def get_driver(driver_type: str) -> DeepAgentsSDKDriver | DeepAgentsCLIDriver:
    if driver_type == "deepagents_sdk":
        return DeepAgentsSDKDriver()
    if driver_type == "deepagents_cli":
        return DeepAgentsCLIDriver()
    raise ValueError(f"Unknown driver: {driver_type!r}")


# ── SDK event normalization ────────────────────────────────────────────────────

def _normalize_sdk_event(event: Any) -> Optional[AgentEvent]:
    """Convert a raw LangGraph/deepagents SDK event to AgentEvent."""
    event_type = getattr(event, "event", None) or "unknown"

    if event_type in ("on_chat_model_stream", "on_llm_stream"):
        content = ""
        if hasattr(event, "data"):
            chunk = event.data.get("chunk")
            if chunk and hasattr(chunk, "content"):
                content = chunk.content
        if content:
            return AgentEvent(type="delta", data={"text": content})

    elif event_type == "on_tool_start":
        data = getattr(event, "data", {})
        return AgentEvent(
            type="tool_call",
            data={"name": data.get("name", "unknown"), "arguments": data.get("input", {})},
        )

    elif event_type == "on_tool_end":
        data = getattr(event, "data", {})
        return AgentEvent(
            type="tool_result",
            data={
                "name": data.get("name", "unknown"),
                "result": str(data.get("output", ""))[:2000],
                "is_error": False,
            },
        )

    return None
