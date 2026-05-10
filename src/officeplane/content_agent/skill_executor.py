"""SkillExecutor — runs SKILL.md skills via the LiteLLM-backed agent runtime."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Optional

import litellm

from officeplane.content_agent.model import ModelConfig, model_config_from_env
from officeplane.content_agent.skill_loader import (
    Skill,
    SkillInput,
    discover_skills,
    load_skill,
)

log = logging.getLogger("officeplane.content_agent.skill_executor")


DEFAULT_SKILLS_ROOT = Path(__file__).parent / "skills"


class SkillNotFoundError(KeyError):
    """Raised when a skill name is not in the registry."""


class SkillInputError(ValueError):
    """Raised when invoke() is given inputs that don't match the SKILL.md spec."""


_TYPE_MAP = {
    "string": str,
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
}


class SkillExecutor:
    """Loads SKILL.md skills from disk and dispatches them through LiteLLM."""

    def __init__(
        self,
        skills_root: Optional[Path] = None,
        model: Optional[ModelConfig] = None,
    ):
        self._skills_root = skills_root or DEFAULT_SKILLS_ROOT
        self._model = model or model_config_from_env()
        self._skills: dict[str, Skill] = {
            s.name: s for s in discover_skills(self._skills_root)
        }

    # ── registry surface ────────────────────────────────────────────────────

    def list_skills(self) -> list[Skill]:
        return list(self._skills.values())

    def get_skill(self, name: str) -> Skill:
        try:
            return self._skills[name]
        except KeyError as exc:
            raise SkillNotFoundError(name) from exc

    def reload(self) -> None:
        """Re-scan the filesystem; useful when SKILL.md files change at runtime."""
        self._skills = {s.name: s for s in discover_skills(self._skills_root)}

    # ── input validation ────────────────────────────────────────────────────

    def validate_inputs(self, skill_name: str, inputs: dict[str, Any]) -> None:
        skill = self.get_skill(skill_name)
        for spec in skill.inputs:
            if spec.required and spec.name not in inputs:
                raise SkillInputError(
                    f"{skill_name}: missing required input '{spec.name}'"
                )
            if spec.name in inputs:
                expected = _TYPE_MAP.get(spec.type)
                if expected and not isinstance(inputs[spec.name], expected):
                    raise SkillInputError(
                        f"{skill_name}.{spec.name}: expected type {spec.type}, "
                        f"got {type(inputs[spec.name]).__name__}"
                    )

    # ── execution ───────────────────────────────────────────────────────────

    async def invoke(
        self,
        skill_name: str,
        inputs: dict[str, Any],
        *,
        actor_id: Optional[str] = None,
        document_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute a skill end-to-end. Returns the parsed JSON output."""
        skill = self.get_skill(skill_name)
        self.validate_inputs(skill_name, inputs)

        system_prompt = self._build_system_prompt(skill)
        user_message = self._build_user_message(skill, inputs)

        log.info("invoking skill %s", skill_name)
        response = await litellm.acompletion(
            model=self._model.model,
            temperature=self._model.temperature,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        raw = response.choices[0].message.content or ""
        output = self._parse_json_response(raw)

        await self._emit_audit(
            skill,
            output,
            actor_id=actor_id,
            document_id=document_id,
        )
        return output

    # ── internals ───────────────────────────────────────────────────────────

    def _build_system_prompt(self, skill: Skill) -> str:
        outputs_schema = "\n".join(
            f"- {o.name} ({o.type}): {o.description or '...'}" for o in skill.outputs
        ) or "(no declared outputs — emit any well-formed JSON object)"
        return (
            f"You are executing the OfficePlane skill '{skill.name}'.\n"
            f"\n--- SKILL DEFINITION ---\n{skill.body}\n--- END SKILL ---\n\n"
            f"Required outputs:\n{outputs_schema}\n\n"
            "Respond with a single JSON object. No prose, no markdown fences, no commentary."
        )

    def _build_user_message(self, skill: Skill, inputs: dict[str, Any]) -> str:
        return f"Inputs for {skill.name}:\n{json.dumps(inputs, indent=2)}"

    def _parse_json_response(self, raw: str) -> dict[str, Any]:
        text = raw.strip()
        if text.startswith("```"):
            # Strip ```json ... ``` fences
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            log.warning("skill output not valid JSON: %s", exc)
            return {"raw": raw}
        if not isinstance(parsed, dict):
            return {"value": parsed}
        return parsed

    async def _emit_audit(
        self,
        skill: Skill,
        output: dict[str, Any],
        *,
        actor_id: Optional[str],
        document_id: Optional[str],
    ) -> None:
        """Write an ExecutionHistory row. Soft-fails on DB error so a transient
        DB outage doesn't break the agent."""
        try:
            from prisma import Prisma

            db = Prisma()
            await db.connect()
            try:
                await db.executionhistory.create(
                    data={
                        "eventType": "SYSTEM_STARTUP",  # TODO Phase 6: add SKILL_INVOKED
                        "eventMessage": f"skill:{skill.name}",
                        "documentId": document_id,
                        "actorType": "agent",
                        "actorId": actor_id,
                        "metadata": {"skill": skill.name, "output_keys": list(output)},
                    }
                )
            finally:
                await db.disconnect()
        except Exception as exc:  # pragma: no cover — observability soft-fail
            log.warning("audit emit failed for %s: %s", skill.name, exc)
