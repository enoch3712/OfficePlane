"""Tests for the generate-pdf skill handler (Phase 17 — PDF export)."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import importlib.util
import sys
import pytest


def _load_handler():
    p = Path("/app/src/officeplane/content_agent/skills/generate-pdf/handler.py")
    if not p.exists():
        p = Path(__file__).parents[2] / "src/officeplane/content_agent/skills/generate-pdf/handler.py"
    spec = importlib.util.spec_from_file_location("gpdf_handler", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gpdf_handler"] = mod
    spec.loader.exec_module(mod)
    return mod


def _llm(s):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=s))])


def test_handler_renders_real_pdf(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    fake = json.dumps({
        "type": "document", "meta": {"title": "BP PDF"},
        "children": [
            {"type": "section", "id": "s1", "level": 1, "heading": "Intro",
             "children": [{"type": "paragraph", "text": "BP matters."}]}
        ],
        "attributions": [],
    })

    async def _run():
        with patch.object(mod, "_load_sources", new=AsyncMock(return_value=[
            {"document_id": "d", "title": "Src", "summary": "", "topics": [], "chapters": []}
        ])):
            with patch("litellm.acompletion", new=AsyncMock(return_value=_llm(fake))):
                with patch.object(mod, "persist_initial_revision", new=AsyncMock(return_value=None)):
                    with patch.object(mod, "persist_derivations_from_document", new=AsyncMock(return_value=0)):
                        with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                            return await mod.execute(inputs={
                                "source_document_ids": ["d"], "brief": "Make PDF"
                            })

    r = asyncio.run(_run())
    assert r["file_path"].endswith("output.pdf")
    assert Path(r["file_path"]).exists()
    head = Path(r["file_path"]).read_bytes()[:5]
    assert head == b"%PDF-"


def test_handler_validates_inputs():
    mod = _load_handler()

    async def _run(i):
        return await mod.execute(inputs=i)

    with pytest.raises(ValueError, match="source_document_ids"):
        asyncio.run(_run({"source_document_ids": [], "brief": "x"}))
    with pytest.raises(ValueError, match="brief"):
        asyncio.run(_run({"source_document_ids": ["a"], "brief": ""}))
