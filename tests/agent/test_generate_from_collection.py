import asyncio
import json
import pytest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, AsyncMock
import importlib.util
import sys


def _load_handler():
    p = Path("/app/src/officeplane/content_agent/skills/generate-from-collection/handler.py")
    if not p.exists():
        p = (
            Path(__file__).parents[2]
            / "src/officeplane/content_agent/skills/generate-from-collection/handler.py"
        )
    spec = importlib.util.spec_from_file_location("gfc_handler", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["gfc_handler"] = mod
    spec.loader.exec_module(mod)
    return mod


def _llm(json_str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=json_str))]
    )


def test_validates_inputs():
    mod = _load_handler()

    async def _run(inputs):
        return await mod.execute(inputs=inputs)

    with pytest.raises(ValueError, match="format"):
        asyncio.run(_run({"source_document_ids": ["a"], "brief": "x", "format": "junk"}))
    with pytest.raises(ValueError, match="brief"):
        asyncio.run(_run({"source_document_ids": ["a"], "brief": ""}))
    with pytest.raises(ValueError, match="collection_id or source_document_ids"):
        asyncio.run(_run({"brief": "x"}))


def test_handles_explicit_ids_docx(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    fake = json.dumps({
        "type": "document",
        "meta": {"title": "Combined"},
        "children": [
            {
                "type": "section",
                "id": "s1",
                "level": 1,
                "heading": "Intro",
                "children": [{"type": "paragraph", "id": "p1", "text": "..."}],
            }
        ],
        "attributions": [{"node_id": "p1", "document_id": "src-1"}],
    })

    async def _run():
        with patch.object(
            mod,
            "_load_sources",
            new=AsyncMock(
                return_value=[
                    {
                        "document_id": "src-1",
                        "title": "A",
                        "summary": "",
                        "topics": [],
                        "chapters": [],
                    },
                    {
                        "document_id": "src-2",
                        "title": "B",
                        "summary": "",
                        "topics": [],
                        "chapters": [],
                    },
                ]
            ),
        ):
            with patch("litellm.acompletion", new=AsyncMock(return_value=_llm(fake))):
                with patch.object(
                    mod, "persist_initial_revision", new=AsyncMock(return_value=None)
                ):
                    with patch.object(
                        mod,
                        "persist_derivations_from_document",
                        new=AsyncMock(return_value=0),
                    ):
                        with patch.object(
                            mod,
                            "persist_skill_invocation",
                            new=AsyncMock(return_value=None),
                        ):
                            return await mod.execute(
                                inputs={
                                    "source_document_ids": ["src-1", "src-2"],
                                    "brief": "Combined doc",
                                    "format": "docx",
                                }
                            )

    r = asyncio.run(_run())
    assert r["format"] == "docx"
    assert r["source_document_count"] == 2
    assert r["file_path"].endswith("output.docx")
    assert Path(r["file_path"]).exists()


def test_handles_collection_id(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    fake = json.dumps(
        {"type": "document", "meta": {"title": "T"}, "children": [], "attributions": []}
    )

    async def _run():
        with patch.object(
            mod,
            "_resolve_collection_documents",
            new=AsyncMock(return_value=["a", "b"]),
        ):
            with patch.object(
                mod,
                "_load_sources",
                new=AsyncMock(
                    return_value=[
                        {
                            "document_id": "a",
                            "title": "X",
                            "summary": "",
                            "topics": [],
                            "chapters": [],
                        },
                        {
                            "document_id": "b",
                            "title": "Y",
                            "summary": "",
                            "topics": [],
                            "chapters": [],
                        },
                    ]
                ),
            ):
                with patch("litellm.acompletion", new=AsyncMock(return_value=_llm(fake))):
                    with patch.object(
                        mod,
                        "persist_initial_revision",
                        new=AsyncMock(return_value=None),
                    ):
                        with patch.object(
                            mod,
                            "persist_derivations_from_document",
                            new=AsyncMock(return_value=0),
                        ):
                            with patch.object(
                                mod,
                                "persist_skill_invocation",
                                new=AsyncMock(return_value=None),
                            ):
                                return await mod.execute(
                                    inputs={
                                        "collection_id": "col-1",
                                        "brief": "Combine",
                                        "format": "pptx",
                                        "slide_count": 5,
                                    }
                                )

    r = asyncio.run(_run())
    assert r["format"] == "pptx"
    assert r["source_document_count"] == 2
    assert r["file_path"].endswith("output.pptx")
