"""Tests for SkillExecutor (Phase 3.4a)."""
from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from officeplane.content_agent.skill_executor import (
    SkillExecutor,
    SkillNotFoundError,
    SkillInputError,
)


SKILLS_ROOT = Path(__file__).resolve().parents[2] / "src/officeplane/content_agent/skills"


def test_executor_discovers_skills():
    ex = SkillExecutor(skills_root=SKILLS_ROOT)
    names = {s.name for s in ex.list_skills()}
    # All 12 ECM skills + the _example fixture should be present
    assert "audit-query" in names
    assert "document-search" in names
    assert "_example" in names


def test_get_unknown_skill_raises():
    ex = SkillExecutor(skills_root=SKILLS_ROOT)
    with pytest.raises(SkillNotFoundError):
        ex.get_skill("nope-not-real")


def test_validate_inputs_rejects_missing_required():
    ex = SkillExecutor(skills_root=SKILLS_ROOT)
    with pytest.raises(SkillInputError, match="query"):
        ex.validate_inputs("document-search", {})


def test_validate_inputs_accepts_optional_omitted():
    ex = SkillExecutor(skills_root=SKILLS_ROOT)
    # `query` is required; `top_k` and `collection_id` are optional
    ex.validate_inputs("document-search", {"query": "hello"})


def test_validate_inputs_rejects_wrong_type():
    ex = SkillExecutor(skills_root=SKILLS_ROOT)
    with pytest.raises(SkillInputError, match="type"):
        ex.validate_inputs("document-search", {"query": 123})


@pytest.mark.asyncio
async def test_invoke_calls_litellm_and_parses_json():
    """End-to-end: invoke runs the LLM call (mocked) and returns parsed output."""
    ex = SkillExecutor(skills_root=SKILLS_ROOT)

    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content='{"results": [{"title": "Doc A"}]}'))]

    with patch(
        "officeplane.content_agent.skill_executor.litellm.acompletion",
        new=AsyncMock(return_value=fake_response),
    ):
        with patch(
            "officeplane.content_agent.skill_executor.SkillExecutor._emit_audit",
            new=AsyncMock(),
        ):
            output = await ex.invoke("document-search", {"query": "hello"})

    assert output == {"results": [{"title": "Doc A"}]}


@pytest.mark.asyncio
async def test_invoke_strips_markdown_code_fences():
    """LLMs sometimes wrap JSON in ```json fences; the executor should strip them."""
    ex = SkillExecutor(skills_root=SKILLS_ROOT)

    fenced = '```json\n{"events": []}\n```'
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content=fenced))]

    with patch(
        "officeplane.content_agent.skill_executor.litellm.acompletion",
        new=AsyncMock(return_value=fake_response),
    ):
        with patch(
            "officeplane.content_agent.skill_executor.SkillExecutor._emit_audit",
            new=AsyncMock(),
        ):
            output = await ex.invoke("audit-query", {"filters": {}})

    assert output == {"events": []}


@pytest.mark.asyncio
async def test_invoke_unknown_skill_raises():
    ex = SkillExecutor(skills_root=SKILLS_ROOT)
    with pytest.raises(SkillNotFoundError):
        await ex.invoke("nope", {})
