"""
Skill base classes.

A Skill is a self-contained agent pipeline that bundles:
  - system prompt / instructions
  - driver preference (SDK vs CLI)
  - run logic
  - deterministic post-run validation
  - optional second-pass quality check

Usage:
    class MySkill(Skill):
        name = "my-skill"
        description = "Does something useful"
        default_driver = "deepagents_cli"

        async def run(self, ctx: SkillContext) -> SkillResult:
            ...

        async def validate(self, ctx, result) -> list[str]:
            ...  # return [] on success, error strings on failure
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Optional, Type

from pydantic import BaseModel


@dataclass
class SkillContext:
    """Runtime context passed to every skill execution."""

    job_id: str
    workspace: Path
    model: str
    driver: str
    params: dict[str, Any]
    session_id: Optional[str] = None  # set when part of an ECM session


@dataclass
class SkillResult:
    """Outcome of a skill execution."""

    status: str  # "completed" | "failed"
    output: dict[str, Any] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    quality_passed: bool = True

    @classmethod
    def success(cls, **output: Any) -> "SkillResult":
        return cls(status="completed", output=output)

    @classmethod
    def failure(cls, *errors: str) -> "SkillResult":
        return cls(status="failed", errors=list(errors))

    @property
    def succeeded(self) -> bool:
        return self.status == "completed"


class Skill(ABC):
    """Abstract base for all skills."""

    name: ClassVar[str]
    description: ClassVar[str]
    default_driver: ClassVar[str] = "deepagents_sdk"

    # Override with a Pydantic model to document + validate skill-specific params
    params_schema: ClassVar[Optional[Type[BaseModel]]] = None

    @abstractmethod
    async def run(self, ctx: SkillContext) -> SkillResult:
        """Execute the skill's main agent loop."""
        ...

    async def validate(self, ctx: SkillContext, result: SkillResult) -> list[str]:
        """
        Deterministic post-run validation.
        Returns a list of error strings (empty = passed).
        """
        return []

    async def quality_check(self, ctx: SkillContext, result: SkillResult) -> SkillResult:
        """
        Optional second-pass agent quality review.
        Default is a no-op; override to add review/regeneration logic.
        """
        return result

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "default_driver": self.default_driver,
            "params_schema": (
                self.params_schema.model_json_schema() if self.params_schema else None
            ),
        }
