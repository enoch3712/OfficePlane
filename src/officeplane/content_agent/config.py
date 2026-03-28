"""Configuration for the content generation agent."""

import os
from dataclasses import dataclass, field


@dataclass
class ContentAgentConfig:
    """Configuration for content generation."""

    # LLM settings
    model: str = field(
        default_factory=lambda: os.getenv("CONTENT_AGENT_MODEL", "gpt-4o")
    )
    temperature: float = 0.7
    max_tokens: int = 16384

    # Workspace
    workspace_root: str = field(
        default_factory=lambda: os.getenv("CONTENT_AGENT_WORKSPACE", "/data/workspaces")
    )

    # Timeouts
    job_timeout_seconds: int = field(
        default_factory=lambda: int(os.getenv("CONTENT_AGENT_TIMEOUT", "600"))
    )

    # Output
    default_output_format: str = "pptx"

    @classmethod
    def from_env(cls) -> "ContentAgentConfig":
        return cls()
