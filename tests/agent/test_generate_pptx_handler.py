"""Tests for the generate-pptx skill handler."""
import asyncio
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import pytest
import importlib.util, sys


def _load_handler():
    p = Path("/app/src/officeplane/content_agent/skills/generate-pptx/handler.py")
    if not p.exists():
        p = Path(__file__).parents[2] / "src/officeplane/content_agent/skills/generate-pptx/handler.py"
    spec = importlib.util.spec_from_file_location("gp_handler", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gp_handler"] = mod
    spec.loader.exec_module(mod)
    return mod


def _llm(json_str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json_str))])


def test_handler_respects_slide_count(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))

    # Have the LLM emit 20 sections; cap = 8.
    sections = [
        {"type": "section", "id": f"s{i}", "level": 1, "heading": f"S{i}",
         "children": [{"type": "paragraph", "text": "x"}]}
        for i in range(20)
    ]
    fake_json = json.dumps({
        "type": "document",
        "meta": {"title": "BP Deck", "render_hints": {"max_slides": 8}},
        "children": sections,
        "attributions": [],
    })

    async def _run():
        with patch.object(mod, "_load_sources", new=AsyncMock(return_value=[
            {"document_id": "doc-1", "title": "src", "summary": "", "topics": [], "chapters": []}
        ])):
            with patch("litellm.acompletion", new=AsyncMock(return_value=_llm(fake_json))):
                return await mod.execute(inputs={
                    "source_document_ids": ["doc-1"],
                    "brief": "Onboard nurses",
                    "slide_count": 8,
                    "style": "clinical",
                    "audience": "RNs",
                    "tone": "concise",
                })

    r = asyncio.run(_run())
    assert r["file_path"].endswith("output.pptx")
    assert Path(r["file_path"]).exists()
    assert r["slide_count"] <= 8
    assert r["title"] == "BP Deck"


def test_handler_threads_params_into_prompt(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))

    captured = {}

    async def _fake_completion(**kwargs):
        captured["messages"] = kwargs["messages"]
        return _llm(json.dumps({"type": "document", "meta": {"title": "T"}, "children": [], "attributions": []}))

    async def _run():
        with patch.object(mod, "_load_sources", new=AsyncMock(return_value=[
            {"document_id": "x", "title": "src", "summary": "", "topics": [], "chapters": []}
        ])):
            with patch("litellm.acompletion", new=_fake_completion):
                await mod.execute(inputs={
                    "source_document_ids": ["x"],
                    "brief": "Foo",
                    "slide_count": 12,
                    "style": "clinical",
                    "audience": "nurses",
                    "tone": "warm",
                })

    asyncio.run(_run())
    p = captured["messages"][0]["content"]
    assert "clinical" in p
    assert "nurses" in p
    assert "warm" in p
    assert "12" in p


def test_handler_validates_inputs():
    mod = _load_handler()

    async def _run(inputs):
        return await mod.execute(inputs=inputs)

    with pytest.raises(ValueError, match="source_document_ids"):
        asyncio.run(_run({"source_document_ids": [], "brief": "x"}))
    with pytest.raises(ValueError, match="brief"):
        asyncio.run(_run({"source_document_ids": ["a"], "brief": ""}))
    with pytest.raises(ValueError, match="slide_count"):
        asyncio.run(_run({"source_document_ids": ["a"], "brief": "x", "slide_count": 0}))
    with pytest.raises(ValueError, match="slide_count"):
        asyncio.run(_run({"source_document_ids": ["a"], "brief": "x", "slide_count": 101}))
