import asyncio, json, importlib.util, sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
import pytest


def _load_handler():
    p = Path("/app/src/officeplane/content_agent/skills/rewrite-node/handler.py")
    if not p.exists():
        p = Path(__file__).parents[2] / "src/officeplane/content_agent/skills/rewrite-node/handler.py"
    spec = importlib.util.spec_from_file_location("rn_handler", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["rn_handler"] = mod
    spec.loader.exec_module(mod)
    return mod


def _seed_workspace(tmp_path: Path, ws: str, doc: dict) -> Path:
    workspace = tmp_path / ws
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "document.json").write_text(json.dumps(doc))
    return workspace


def _llm(content: str):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


def test_validates_inputs():
    mod = _load_handler()
    async def _run(i): return await mod.execute(inputs=i)
    with pytest.raises(ValueError, match="workspace_id"):
        asyncio.run(_run({"node_id": "p1", "instruction": "x"}))
    with pytest.raises(ValueError, match="node_id"):
        asyncio.run(_run({"workspace_id": "ws", "instruction": "x"}))
    with pytest.raises(ValueError, match="instruction"):
        asyncio.run(_run({"workspace_id": "ws", "node_id": "p1"}))


def test_missing_workspace_raises(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        asyncio.run(mod.execute(inputs={
            "workspace_id": "nope", "node_id": "p1", "instruction": "x",
        }))


def test_missing_node_raises(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    _seed_workspace(tmp_path, "ws1", {
        "type": "document", "meta": {"title": "T"},
        "children": [{"type": "paragraph", "id": "p1", "text": "hi"}],
        "attributions": [],
    })
    with pytest.raises(ValueError, match="not found"):
        asyncio.run(mod.execute(inputs={
            "workspace_id": "ws1", "node_id": "missing", "instruction": "make it nicer",
        }))


def test_rejects_non_rewritable_type(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    _seed_workspace(tmp_path, "ws1", {
        "type": "document", "meta": {"title": "T"},
        "children": [{"type": "table", "id": "t1", "headers": ["a"], "rows": [["b"]]}],
        "attributions": [],
    })
    with pytest.raises(ValueError, match="not rewritable"):
        asyncio.run(mod.execute(inputs={
            "workspace_id": "ws1", "node_id": "t1", "instruction": "x",
        }))


def test_rewrites_paragraph_and_preserves_id_type(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    _seed_workspace(tmp_path, "ws1", {
        "type": "document", "meta": {"title": "T"},
        "children": [
            {"type": "section", "id": "s1", "level": 1, "heading": "Intro", "children": [
                {"type": "paragraph", "id": "p0", "text": "before"},
                {"type": "paragraph", "id": "p1", "text": "Cuff size matters."},
                {"type": "paragraph", "id": "p2", "text": "after"},
            ]}
        ],
        "attributions": [],
    })

    # LLM tries to switch the id and type — should be overwritten back to originals
    rewritten = json.dumps({"id": "WRONG", "type": "heading", "text": "Selecting the correct cuff size is critical."})
    async def _run():
        with patch("litellm.acompletion", new=AsyncMock(return_value=_llm(rewritten))):
            with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                return await mod.execute(inputs={
                    "workspace_id": "ws1", "node_id": "p1",
                    "instruction": "rewrite more clinically",
                })
    r = asyncio.run(_run())
    assert r["node_id"] == "p1"
    assert r["original_node"]["text"] == "Cuff size matters."
    assert r["rewritten_node"]["id"] == "p1"        # forced back
    assert r["rewritten_node"]["type"] == "paragraph"  # forced back
    assert "cuff" in r["rewritten_node"]["text"].lower()
    # Crucial: handler does NOT write back to document.json (caller applies via document-edit)
    after = json.loads((tmp_path / "ws1" / "document.json").read_text())
    p1_text = after["children"][0]["children"][1]["text"]
    assert p1_text == "Cuff size matters."  # unchanged on disk


def test_find_node_with_context_picks_neighbours(tmp_path, monkeypatch):
    mod = _load_handler()
    doc = {
        "type": "document",
        "children": [
            {"type": "section", "id": "s1", "level": 1, "heading": "X", "children": [
                {"type": "paragraph", "id": "p0", "text": "zero"},
                {"type": "paragraph", "id": "p1", "text": "one"},
                {"type": "paragraph", "id": "p2", "text": "two"},
                {"type": "paragraph", "id": "p3", "text": "three"},
            ]}
        ],
    }
    target, neighbours, parent = mod._find_node_with_context(doc, "p2")
    assert target is not None and target["id"] == "p2"
    n_ids = [n["id"] for n in neighbours]
    assert "p1" in n_ids and "p3" in n_ids
    assert parent is not None and parent.get("heading") == "X"
