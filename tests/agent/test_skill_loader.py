"""Tests for the filesystem SKILL.md loader."""
from __future__ import annotations

from pathlib import Path

import pytest

from officeplane.content_agent.skill_loader import (
    Skill,
    SkillInput,
    SkillOutput,
    discover_skills,
    load_skill,
)


SKILLS_ROOT = Path(__file__).resolve().parents[2] / "src/officeplane/content_agent/skills"


def test_load_single_skill():
    skill = load_skill(SKILLS_ROOT / "_example")
    assert skill.name == "_example"
    assert skill.description.startswith("Test fixture")
    assert skill.inputs == [SkillInput(name="query", type="string", required=True)]
    assert skill.outputs == [SkillOutput(name="result", type="string")]
    assert skill.tools == []
    assert skill.body.startswith("# Example skill")


def test_discover_finds_example():
    skills = discover_skills(SKILLS_ROOT)
    names = [s.name for s in skills]
    assert "_example" in names


def test_discover_ignores_python_files():
    """Old Python-class skills (generate_docx.py etc) must NOT be picked up."""
    skills = discover_skills(SKILLS_ROOT)
    for s in skills:
        assert s.path is not None
        assert (s.path / "SKILL.md").exists(), f"{s.name} missing SKILL.md"


def test_load_missing_skill_md(tmp_path):
    empty = tmp_path / "no_skill_here"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        load_skill(empty)


def test_load_missing_frontmatter(tmp_path):
    bad = tmp_path / "bad_skill"
    bad.mkdir()
    (bad / "SKILL.md").write_text("# No frontmatter here\n")
    with pytest.raises(ValueError, match="frontmatter"):
        load_skill(bad)


def test_skill_dataclasses_are_frozen_compatible():
    """Sanity: dataclasses round-trip through dict() / model construction."""
    s = Skill(name="x", description="y")
    assert s.name == "x"
    assert s.inputs == []
    assert s.outputs == []
    assert s.tools == []
    assert s.body == ""
