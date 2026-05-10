"""Phase 5.2 — assert the full ECM skill catalog reaches the system prompt."""
from __future__ import annotations

from pathlib import Path

from officeplane.content_agent.prompts import build_system_prompt
from officeplane.content_agent.skill_loader import discover_skills


SKILLS_ROOT = Path(__file__).resolve().parents[2] / "src/officeplane/content_agent/skills"

ECM_SKILLS = [
    "document-ingest",
    "document-search",
    "document-classify",
    "document-summarize",
    "document-extract",
    "document-version",
    "document-redact",
    "document-relate",
    "document-export",
    "document-workflow",
    "collection-manage",
    "audit-query",
]


def test_all_twelve_ecm_skills_discovered():
    skills = discover_skills(SKILLS_ROOT)
    names = {s.name for s in skills}
    missing = [s for s in ECM_SKILLS if s not in names]
    assert not missing, f"missing skills: {missing}"


def test_all_twelve_ecm_skills_reach_system_prompt():
    skills = discover_skills(SKILLS_ROOT)
    prompt = build_system_prompt(skills=skills, user_context="")
    for skill in ECM_SKILLS:
        assert skill in prompt, f"{skill} missing from system prompt"


def test_every_ecm_skill_has_description_and_body():
    skills = {s.name: s for s in discover_skills(SKILLS_ROOT)}
    for name in ECM_SKILLS:
        s = skills[name]
        assert s.description, f"{name} missing description"
        assert s.body, f"{name} missing body"
        assert "## When to use" in s.body, f"{name} body missing 'When to use' section"
        assert "## How it works" in s.body, f"{name} body missing 'How it works' section"
        assert "## Audit" in s.body, f"{name} body missing 'Audit' section"
