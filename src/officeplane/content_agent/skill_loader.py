"""Filesystem-based SKILL.md loader.

Each skill is a directory containing a ``SKILL.md`` file with YAML frontmatter
followed by markdown. Skills become product spec: editing the markdown changes
the agent's behaviour without code changes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class SkillInput:
    name: str
    type: str
    required: bool = False
    description: str = ""


@dataclass
class SkillOutput:
    name: str
    type: str
    description: str = ""


@dataclass
class Skill:
    name: str
    description: str = ""
    inputs: list[SkillInput] = field(default_factory=list)
    outputs: list[SkillOutput] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    body: str = ""
    path: Path | None = None


_FRONTMATTER_DELIM = "---"


def load_skill(skill_dir: Path) -> Skill:
    """Load a single skill from ``<skill_dir>/SKILL.md``."""
    md_path = skill_dir / "SKILL.md"
    if not md_path.exists():
        raise FileNotFoundError(f"SKILL.md not found in {skill_dir}")

    raw = md_path.read_text(encoding="utf-8")
    if not raw.lstrip().startswith(_FRONTMATTER_DELIM):
        raise ValueError(f"{md_path}: missing YAML frontmatter delimiter '---'")

    # Split: '', frontmatter, body
    parts = raw.split(_FRONTMATTER_DELIM, 2)
    if len(parts) < 3:
        raise ValueError(f"{md_path}: malformed frontmatter")

    frontmatter_text, body = parts[1], parts[2]
    meta = yaml.safe_load(frontmatter_text) or {}

    return Skill(
        name=meta.get("name", skill_dir.name),
        description=str(meta.get("description", "")),
        inputs=[SkillInput(**i) for i in meta.get("inputs", []) or []],
        outputs=[SkillOutput(**o) for o in meta.get("outputs", []) or []],
        tools=list(meta.get("tools", []) or []),
        body=body.strip(),
        path=skill_dir,
    )


def discover_skills(root: Path) -> list[Skill]:
    """Discover every SKILL.md under ``root`` (one level deep), sorted by name."""
    if not root.exists():
        return []
    skills: list[Skill] = []
    for child in sorted(root.iterdir()):
        if child.is_dir() and (child / "SKILL.md").exists():
            skills.append(load_skill(child))
    return skills
