"""Tests for the generate-docx skill handler (Task 5 of doc-tree refactor)."""
import asyncio
import json
from pathlib import Path
from unittest.mock import patch, AsyncMock
import pytest


def _fake_llm_response(json_str: str):
    """Build a litellm.acompletion-shaped response."""
    from types import SimpleNamespace
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json_str))]
    )


def test_handler_renders_real_docx(tmp_path, monkeypatch):
    import importlib.util, sys
    handler_path = Path("/app/src/officeplane/content_agent/skills/generate-docx/handler.py")
    if not handler_path.exists():
        handler_path = Path(__file__).parents[2] / "src/officeplane/content_agent/skills/generate-docx/handler.py"
    spec = importlib.util.spec_from_file_location("gd_handler", handler_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gd_handler"] = mod
    spec.loader.exec_module(mod)

    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))

    fake_json = json.dumps({
        "type": "document",
        "meta": {"title": "BP Care"},
        "children": [
            {"type": "section", "id": "s1", "level": 1, "heading": "Intro",
             "children": [{"type": "paragraph", "text": "BP measurement matters."}]}
        ],
        "attributions": []
    })

    async def _run():
        with patch.object(mod, "_load_sources", new=AsyncMock(return_value=[
            {"document_id": "doc-1", "title": "src", "summary": "...", "topics": [], "chapters": []}
        ])):
            with patch("litellm.acompletion", new=AsyncMock(return_value=_fake_llm_response(fake_json))):
                return await mod.execute(inputs={
                    "source_document_ids": ["doc-1"],
                    "brief": "Make a BP primer",
                })

    result = asyncio.run(_run())
    assert result["file_path"].endswith("output.docx")
    assert Path(result["file_path"]).exists()
    assert Path(result["file_path"]).stat().st_size > 1000
    assert result["title"] == "BP Care"
    assert result["node_count"] >= 2


def test_handler_validates_inputs(tmp_path, monkeypatch):
    import importlib.util, sys
    handler_path = Path("/app/src/officeplane/content_agent/skills/generate-docx/handler.py")
    if not handler_path.exists():
        handler_path = Path(__file__).parents[2] / "src/officeplane/content_agent/skills/generate-docx/handler.py"
    spec = importlib.util.spec_from_file_location("gd_handler_v", handler_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gd_handler_v"] = mod
    spec.loader.exec_module(mod)

    async def _run(inputs):
        return await mod.execute(inputs=inputs)

    with pytest.raises(ValueError, match="source_document_ids"):
        asyncio.run(_run({"source_document_ids": [], "brief": "x"}))
    with pytest.raises(ValueError, match="brief"):
        asyncio.run(_run({"source_document_ids": ["a"], "brief": ""}))
