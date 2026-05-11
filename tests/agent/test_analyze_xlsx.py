import asyncio
import json
import sys
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest


def _load_handler():
    p = Path("/app/src/officeplane/content_agent/skills/analyze-xlsx/handler.py")
    if not p.exists():
        p = Path(__file__).parents[2] / "src/officeplane/content_agent/skills/analyze-xlsx/handler.py"
    spec = importlib.util.spec_from_file_location("ax_handler", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ax_handler"] = mod
    spec.loader.exec_module(mod)
    return mod


def _llm(json_str: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json_str))])


def test_validates_inputs():
    mod = _load_handler()
    async def _run(i): return await mod.execute(inputs=i)
    with pytest.raises(ValueError, match="document_id"):
        asyncio.run(_run({}))
    with pytest.raises(ValueError, match="max_issues"):
        asyncio.run(_run({"document_id": "x", "max_issues": 0}))
    with pytest.raises(ValueError, match="max_issues"):
        asyncio.run(_run({"document_id": "x", "max_issues": 200}))


def test_normalises_and_caps_issues():
    """Mock the LLM to return issues including invalid categories + extras beyond max."""
    mod = _load_handler()

    fake_doc = SimpleNamespace(
        id="doc-1", title="Q3", sourceFormat="xlsx",
    )
    issues_raw = {
        "issues": [
            {"severity": "high", "category": "formula_error", "sheet": "S1", "cell": "B5",
             "description": "DIV/0", "suggestion": "Guard with IFERROR"},
            {"severity": "WAT", "category": "outlier", "sheet": "S1", "cell": "C9",
             "description": "huge", "suggestion": "verify"},
            {"severity": "low", "category": "bogus_category", "description": "?"},  # dropped
            {"severity": "low", "category": "suspected_typo", "description": "12000 in % col"},
            {"severity": "medium", "category": "missing_total", "sheet": "S2",
             "description": "no total row", "suggestion": "Add =SUM"},
        ]
    }

    async def _run():
        with patch.object(mod, "Prisma") as MockPrisma:
            instance = MockPrisma.return_value
            instance.connect = AsyncMock(return_value=None)
            instance.disconnect = AsyncMock(return_value=None)
            instance.document.find_unique = AsyncMock(return_value=fake_doc)
            instance.chapter.find_many = AsyncMock(return_value=[])
            instance.page.find_many = AsyncMock(return_value=[
                SimpleNamespace(content="## Sheet1\n| A | B |\n|---|---|\n| 1 | 2 |")
            ])
            with patch("litellm.acompletion", new=AsyncMock(return_value=_llm(json.dumps(issues_raw)))):
                with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                    return await mod.execute(inputs={"document_id": "doc-1", "max_issues": 3})

    r = asyncio.run(_run())
    assert r["title"] == "Q3"
    # Cap to 3 (max_issues=3) — only the first 3 valid items, with bogus_category dropped
    assert r["issue_count"] <= 3
    cats = [i["category"] for i in r["issues"]]
    assert "bogus_category" not in cats
    # Severity normalised
    sevs = [i["severity"] for i in r["issues"]]
    for s in sevs:
        assert s in ("high", "medium", "low")


def test_rejects_non_xlsx_document():
    mod = _load_handler()
    fake_doc = SimpleNamespace(id="doc-x", title="Word doc", sourceFormat="docx")

    async def _run():
        with patch.object(mod, "Prisma") as MockPrisma:
            instance = MockPrisma.return_value
            instance.connect = AsyncMock(return_value=None)
            instance.disconnect = AsyncMock(return_value=None)
            instance.document.find_unique = AsyncMock(return_value=fake_doc)
            return await mod.execute(inputs={"document_id": "doc-x"})

    with pytest.raises(ValueError, match="Excel"):
        asyncio.run(_run())


def test_missing_document_raises():
    mod = _load_handler()

    async def _run():
        with patch.object(mod, "Prisma") as MockPrisma:
            instance = MockPrisma.return_value
            instance.connect = AsyncMock(return_value=None)
            instance.disconnect = AsyncMock(return_value=None)
            instance.document.find_unique = AsyncMock(return_value=None)
            return await mod.execute(inputs={"document_id": "missing-id"})

    with pytest.raises(ValueError, match="document not found"):
        asyncio.run(_run())


def test_empty_workbook_returns_empty_list():
    mod = _load_handler()
    fake_doc = SimpleNamespace(id="doc-empty", title="Empty", sourceFormat="xlsx")

    async def _run():
        with patch.object(mod, "Prisma") as MockPrisma:
            instance = MockPrisma.return_value
            instance.connect = AsyncMock(return_value=None)
            instance.disconnect = AsyncMock(return_value=None)
            instance.document.find_unique = AsyncMock(return_value=fake_doc)
            instance.chapter.find_many = AsyncMock(return_value=[])
            instance.page.find_many = AsyncMock(return_value=[])
            return await mod.execute(inputs={"document_id": "doc-empty"})

    r = asyncio.run(_run())
    assert r["sheet_count"] == 0
    assert r["issue_count"] == 0
    assert r["issues"] == []
