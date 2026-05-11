"""Tests for the document-edit skill handler."""

import asyncio
import json
from pathlib import Path
import importlib.util
import sys

import pytest


def _load_handler():
    p = Path("/app/src/officeplane/content_agent/skills/document-edit/handler.py")
    if not p.exists():
        p = (
            Path(__file__).parents[2]
            / "src/officeplane/content_agent/skills/document-edit/handler.py"
        )
    spec = importlib.util.spec_from_file_location("de_handler", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["de_handler"] = mod
    spec.loader.exec_module(mod)
    return mod


def _seed_doc(workspace: Path):
    workspace.mkdir(parents=True, exist_ok=True)
    doc = {
        "type": "document",
        "schema_version": "1.0",
        "meta": {"title": "T", "language": "en"},
        "children": [
            {
                "type": "section",
                "id": "s1",
                "level": 1,
                "heading": "A",
                "children": [
                    {"type": "paragraph", "id": "p1", "text": "first"},
                    {"type": "paragraph", "id": "p2", "text": "second"},
                ],
            },
            {
                "type": "section",
                "id": "s2",
                "level": 1,
                "heading": "B",
                "children": [],
            },
        ],
        "attributions": [],
    }
    (workspace / "document.json").write_text(json.dumps(doc))


def test_insert_after(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    _seed_doc(tmp_path / "ws1")
    r = asyncio.run(
        mod.execute(
            inputs={
                "workspace_id": "ws1",
                "operation": "insert_after",
                "anchor_id": "p1",
                "node": {"type": "paragraph", "id": "pNew", "text": "inserted"},
            }
        )
    )
    after = json.loads((tmp_path / "ws1" / "document.json").read_text())
    ids = [c["id"] for c in after["children"][0]["children"]]
    assert ids == ["p1", "pNew", "p2"]
    assert r["operation"] == "insert_after"
    assert r["affected_node_id"] == "pNew"
    assert r["revision"] == 1


def test_insert_before(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    _seed_doc(tmp_path / "ws1")
    asyncio.run(
        mod.execute(
            inputs={
                "workspace_id": "ws1",
                "operation": "insert_before",
                "anchor_id": "p1",
                "node": {"type": "paragraph", "id": "p0", "text": "zero"},
            }
        )
    )
    after = json.loads((tmp_path / "ws1" / "document.json").read_text())
    assert [c["id"] for c in after["children"][0]["children"]] == ["p0", "p1", "p2"]


def test_insert_as_child(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    _seed_doc(tmp_path / "ws1")
    asyncio.run(
        mod.execute(
            inputs={
                "workspace_id": "ws1",
                "operation": "insert_as_child",
                "parent_id": "s2",
                "node": {"type": "paragraph", "id": "b1", "text": "B body"},
            }
        )
    )
    after = json.loads((tmp_path / "ws1" / "document.json").read_text())
    assert [c["id"] for c in after["children"][1]["children"]] == ["b1"]


def test_replace(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    _seed_doc(tmp_path / "ws1")
    asyncio.run(
        mod.execute(
            inputs={
                "workspace_id": "ws1",
                "operation": "replace",
                "target_id": "p1",
                "node": {"type": "paragraph", "id": "p1", "text": "CHANGED"},
            }
        )
    )
    after = json.loads((tmp_path / "ws1" / "document.json").read_text())
    assert after["children"][0]["children"][0]["text"] == "CHANGED"


def test_delete(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    _seed_doc(tmp_path / "ws1")
    asyncio.run(
        mod.execute(
            inputs={
                "workspace_id": "ws1",
                "operation": "delete",
                "target_id": "p1",
            }
        )
    )
    after = json.loads((tmp_path / "ws1" / "document.json").read_text())
    assert [c["id"] for c in after["children"][0]["children"]] == ["p2"]


def test_invalid_operation_raises(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    _seed_doc(tmp_path / "ws1")
    with pytest.raises(ValueError, match="operation"):
        asyncio.run(mod.execute(inputs={"workspace_id": "ws1", "operation": "WAT"}))


def test_missing_workspace_raises(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        asyncio.run(
            mod.execute(inputs={"workspace_id": "nope", "operation": "delete", "target_id": "x"})
        )
