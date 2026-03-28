"""
Skills discovery API.

GET  /api/skills        — list all registered skills with their param schemas
GET  /api/skills/{name} — details for a specific skill
"""

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("")
async def list_skills():
    """List all registered skills."""
    from officeplane.skills import registry
    return {"skills": registry.list_all()}


@router.get("/{name}")
async def get_skill(name: str):
    """Get details and parameter schema for a skill."""
    from officeplane.skills import registry
    try:
        skill = registry.get(name)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Skill {name!r} not found")
    return skill.to_dict()
