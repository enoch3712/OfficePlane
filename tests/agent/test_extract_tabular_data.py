import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest


def _load_handler():
    p = Path("/app/src/officeplane/content_agent/skills/extract-tabular-data/handler.py")
    if not p.exists():
        p = Path(__file__).parents[2] / "src/officeplane/content_agent/skills/extract-tabular-data/handler.py"
    spec = importlib.util.spec_from_file_location("etd_handler", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["etd_handler"] = mod
    spec.loader.exec_module(mod)
    return mod


def _llm(s: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=s))])


def test_validates_inputs():
    mod = _load_handler()
    async def _run(i): return await mod.execute(inputs=i)
    with pytest.raises(ValueError, match="document_id"):
        asyncio.run(_run({}))
    with pytest.raises(ValueError, match="max_tables"):
        asyncio.run(_run({"document_id": "x", "max_tables": 0}))
    with pytest.raises(ValueError, match="max_tables"):
        asyncio.run(_run({"document_id": "x", "max_tables": 200}))


def test_returns_empty_when_no_pages():
    mod = _load_handler()
    fake_doc = SimpleNamespace(id="d-empty", title="Empty")

    async def _run():
        with patch.object(mod, "Prisma") as MP:
            i = MP.return_value
            i.connect = AsyncMock(return_value=None)
            i.disconnect = AsyncMock(return_value=None)
            i.document.find_unique = AsyncMock(return_value=fake_doc)
            i.chapter.find_many = AsyncMock(return_value=[])
            i.page.find_many = AsyncMock(return_value=[])
            return await mod.execute(inputs={"document_id": "d-empty"})

    r = asyncio.run(_run())
    assert r["table_count"] == 0
    assert r["tables"] == []


def test_normalises_rows_and_filters_malformed():
    mod = _load_handler()
    fake_doc = SimpleNamespace(id="d1", title="Doc")
    llm_payload = json.dumps({
        "tables": [
            {"name": "Revenue", "headers": ["Region", "Revenue", "Growth"],
             "rows": [["NA", 1200, 0.12], ["EU", 900, 0.08]],
             "source_page": 1, "source_section_id": "sec-1"},
            # Malformed: rows isn't a list
            {"name": "Bad", "headers": ["A"], "rows": "not-a-list"},
            # Malformed: no headers
            {"name": "Headerless", "rows": [["x"]]},
            # Padded: row shorter than headers — should be padded with None
            {"name": "Padded", "headers": ["A", "B", "C"],
             "rows": [[1, 2], [3, 4, 5]]},
        ]
    })

    async def _run():
        with patch.object(mod, "Prisma") as MP:
            i = MP.return_value
            i.connect = AsyncMock(return_value=None)
            i.disconnect = AsyncMock(return_value=None)
            i.document.find_unique = AsyncMock(return_value=fake_doc)
            i.chapter.find_many = AsyncMock(return_value=[])
            i.page.find_many = AsyncMock(return_value=[
                SimpleNamespace(pageNumber=1, content="## Page 1\n| Region | Rev | Growth |\n|---|---|---|\n| NA | 1200 | 0.12 |")
            ])
            with patch("litellm.acompletion", new=AsyncMock(return_value=_llm(llm_payload))):
                with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                    return await mod.execute(inputs={"document_id": "d1"})

    r = asyncio.run(_run())
    names = [t["name"] for t in r["tables"]]
    assert "Revenue" in names
    assert "Bad" not in names
    assert "Headerless" not in names
    assert "Padded" in names
    padded = next(t for t in r["tables"] if t["name"] == "Padded")
    # Width forced to 3, padded with None
    assert all(len(r) == 3 for r in padded["rows"])
    assert padded["rows"][0] == [1, 2, None]
    assert padded["rows"][1] == [3, 4, 5]


def test_caps_at_max_tables():
    mod = _load_handler()
    fake_doc = SimpleNamespace(id="d2", title="Doc")
    many = json.dumps({
        "tables": [
            {"name": f"T{i}", "headers": ["a"], "rows": [["x"]], "source_page": 1}
            for i in range(50)
        ]
    })

    async def _run():
        with patch.object(mod, "Prisma") as MP:
            i = MP.return_value
            i.connect = AsyncMock(return_value=None)
            i.disconnect = AsyncMock(return_value=None)
            i.document.find_unique = AsyncMock(return_value=fake_doc)
            i.chapter.find_many = AsyncMock(return_value=[])
            i.page.find_many = AsyncMock(return_value=[
                SimpleNamespace(pageNumber=1, content="x")
            ])
            with patch("litellm.acompletion", new=AsyncMock(return_value=_llm(many))):
                with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                    return await mod.execute(inputs={"document_id": "d2", "max_tables": 5})

    r = asyncio.run(_run())
    assert r["table_count"] == 5
    assert len(r["tables"]) == 5


def test_attribution_includes_source_page_and_section():
    mod = _load_handler()
    fake_doc = SimpleNamespace(id="d3", title="Doc")
    payload = json.dumps({
        "tables": [
            {"name": "Q3", "headers": ["A"], "rows": [["x"]],
             "source_page": 4, "source_section_id": "sec-abc"},
        ]
    })

    async def _run():
        with patch.object(mod, "Prisma") as MP:
            i = MP.return_value
            i.connect = AsyncMock(return_value=None)
            i.disconnect = AsyncMock(return_value=None)
            i.document.find_unique = AsyncMock(return_value=fake_doc)
            i.chapter.find_many = AsyncMock(return_value=[])
            i.page.find_many = AsyncMock(return_value=[
                SimpleNamespace(pageNumber=4, content="page 4 content")
            ])
            with patch("litellm.acompletion", new=AsyncMock(return_value=_llm(payload))):
                with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                    return await mod.execute(inputs={"document_id": "d3"})

    r = asyncio.run(_run())
    t = r["tables"][0]
    assert t["source_page"] == 4
    assert t["attribution"]["document_id"] == "d3"
    assert t["attribution"]["section_id"] == "sec-abc"
    assert t["attribution"]["page_numbers"] == [4]


def test_missing_document_raises():
    mod = _load_handler()
    async def _run():
        with patch.object(mod, "Prisma") as MP:
            i = MP.return_value
            i.connect = AsyncMock(return_value=None)
            i.disconnect = AsyncMock(return_value=None)
            i.document.find_unique = AsyncMock(return_value=None)
            return await mod.execute(inputs={"document_id": "missing"})
    with pytest.raises(ValueError, match="document not found"):
        asyncio.run(_run())
