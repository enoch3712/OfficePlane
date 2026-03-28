"""
Skill registry — central catalog of all available skills.

Skills are registered at import time via _bootstrap().
Use get() to retrieve a skill by name and list_all() for discovery.
"""

from __future__ import annotations

from officeplane.skills.base import Skill

_registry: dict[str, Skill] = {}


def register(skill: Skill) -> None:
    """Register a skill instance."""
    _registry[skill.name] = skill


def get(name: str) -> Skill:
    """Retrieve a skill by name. Raises KeyError if not found."""
    skill = _registry.get(name)
    if skill is None:
        available = list(_registry)
        raise KeyError(f"Unknown skill: {name!r}. Available: {available}")
    return skill


def list_all() -> list[dict]:
    """Return serialized metadata for all registered skills."""
    return [s.to_dict() for s in _registry.values()]


def _bootstrap() -> None:
    """Auto-register all built-in skills."""
    from officeplane.skills.generate_pptx import GeneratePPTXSkill
    from officeplane.skills.generate_docx import GenerateDOCXSkill
    from officeplane.skills.team import TeamSkill

    for skill in [GeneratePPTXSkill(), GenerateDOCXSkill(), TeamSkill()]:
        register(skill)


_bootstrap()
