"""Tests for build_system_prompt — Phase 4.2."""
from __future__ import annotations

from pathlib import Path

import pytest

from officeplane.content_agent.prompts import build_system_prompt
from officeplane.content_agent.skill_loader import Skill, SkillInput, discover_skills


SKILLS_ROOT = Path(__file__).resolve().parents[2] / "src/officeplane/content_agent/skills"


def test_prompt_includes_skill_index_and_body():
    skills = [
        Skill(
            name="search-docs",
            description="Search the doc store",
            inputs=[SkillInput(name="query", type="string", required=True)],
            tools=["vector-search"],
            body="# search-docs\n\nUse this when the user asks a question.",
        ),
        Skill(
            name="ingest-doc",
            description="Ingest a new document",
            body="# ingest-doc\n\nUpload + parse + persist.",
        ),
    ]
    prompt = build_system_prompt(skills=skills, user_context="Acme Corp tenant")

    # Skill names appear in the index section
    assert "- search-docs:" in prompt
    assert "- ingest-doc:" in prompt
    # Descriptions follow the names
    assert "Search the doc store" in prompt
    assert "Ingest a new document" in prompt
    # Bodies appear in the detail section
    assert "Use this when the user asks a question." in prompt
    assert "Upload + parse + persist." in prompt
    # User context appears
    assert "Acme Corp tenant" in prompt


def test_prompt_with_no_skills_still_renders():
    prompt = build_system_prompt(skills=[], user_context="")
    # Should not raise and should still contain core instructions
    assert isinstance(prompt, str)
    assert len(prompt) > 0


def test_prompt_real_filesystem_smoke():
    """Smoke: discovered skills (just the _example fixture so far) flow through."""
    skills = discover_skills(SKILLS_ROOT)
    prompt = build_system_prompt(skills=skills, user_context="")
    # Should contain at least the example fixture
    assert "_example" in prompt
