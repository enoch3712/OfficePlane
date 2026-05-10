"""Skills discovery API.

Lists both legacy Python skills (officeplane.skills.registry) and
the new SKILL.md filesystem skills (SkillExecutor). New SKILL.md skills
take precedence on name conflicts.
"""

from fastapi import APIRouter, HTTPException

from officeplane.content_agent.skill_executor import (
    SkillExecutor,
    SkillNotFoundError,
)

router = APIRouter(prefix="/api/skills", tags=["skills"])

_executor = SkillExecutor()


def _skill_md_to_dict(skill) -> dict:
    """Convert a SKILL.md Skill dataclass to the API shape."""
    return {
        "name": skill.name,
        "description": skill.description,
        "source": "skill_md",
        "inputs": [
            {
                "name": i.name,
                "type": i.type,
                "required": i.required,
                "description": i.description,
            }
            for i in skill.inputs
        ],
        "outputs": [
            {"name": o.name, "type": o.type, "description": o.description}
            for o in skill.outputs
        ],
        "tools": list(skill.tools),
    }


@router.get("")
async def list_skills():
    """Union of legacy + SKILL.md skills, SKILL.md takes precedence on name."""
    from officeplane.skills import registry

    skill_md = {s.name: _skill_md_to_dict(s) for s in _executor.list_skills()}
    legacy = {}
    for entry in registry.list_all():
        d = dict(entry)
        d.setdefault("source", "legacy")
        legacy[entry["name"]] = d

    merged = {**legacy, **skill_md}
    return {"skills": list(merged.values())}


@router.get("/{name}")
async def get_skill(name: str):
    """Resolve SKILL.md first, fall back to legacy registry."""
    try:
        return _skill_md_to_dict(_executor.get_skill(name))
    except SkillNotFoundError:
        pass

    from officeplane.skills import registry

    try:
        skill = registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Skill {name!r} not found")
    d = skill.to_dict()
    d.setdefault("source", "legacy")
    return d
