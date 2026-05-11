import asyncio, json, importlib.util, sys
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest


def _load_handler():
    p = Path("/app/src/officeplane/content_agent/skills/citation-validator/handler.py")
    if not p.exists():
        p = Path(__file__).parents[2] / "src/officeplane/content_agent/skills/citation-validator/handler.py"
    spec = importlib.util.spec_from_file_location("cv_handler", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["cv_handler"] = mod
    spec.loader.exec_module(mod)
    return mod


def _seed_workspace(tmp_path: Path, ws: str, doc: dict) -> Path:
    workspace = tmp_path / ws
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "document.json").write_text(json.dumps(doc))
    return workspace


def test_validates_inputs():
    mod = _load_handler()
    async def _run(i): return await mod.execute(inputs=i)
    with pytest.raises(ValueError, match="workspace_id"):
        asyncio.run(_run({}))
    with pytest.raises(ValueError, match="threshold"):
        asyncio.run(_run({"workspace_id": "x", "similarity_threshold": 1.5}))


def test_missing_workspace_raises(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    with pytest.raises(FileNotFoundError):
        asyncio.run(mod.execute(inputs={"workspace_id": "nope"}))


def test_no_attributions_returns_empty(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    _seed_workspace(tmp_path, "ws1", {
        "type": "document", "meta": {"title": "T"}, "children": [], "attributions": []
    })
    r = asyncio.run(mod.execute(inputs={"workspace_id": "ws1"}))
    assert r["validated_count"] == 0
    assert r["unsupported_count"] == 0
    assert r["overall_confidence"] == 0.0


def test_flags_unsupported_when_similarity_low(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    _seed_workspace(tmp_path, "ws1", {
        "type": "document", "meta": {"title": "T"},
        "children": [{"type": "paragraph", "id": "p1", "text": "Cuff size matters."}],
        "attributions": [{"node_id": "p1", "document_id": "d", "section_id": "s"}],
    })

    class FakeProvider:
        async def embed_batch(self, texts):
            # Return orthogonal vectors → cosine ≈ 0
            return [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0]]

    async def _run():
        with patch.object(mod, "get_embedding_provider", return_value=FakeProvider()):
            with patch.object(mod, "_get_source_excerpt", new=AsyncMock(return_value="Marketing budget review")):
                with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                    from prisma import Prisma
                    with patch.object(Prisma, "connect", new=AsyncMock(return_value=None)):
                        with patch.object(Prisma, "disconnect", new=AsyncMock(return_value=None)):
                            return await mod.execute(inputs={"workspace_id": "ws1"})

    r = asyncio.run(_run())
    assert r["validated_count"] == 1
    assert r["unsupported_count"] == 1  # below threshold
    assert r["per_node"][0]["supported"] is False
    assert r["per_node"][0]["similarity"] < 0.55


def test_supports_when_similarity_high(tmp_path, monkeypatch):
    mod = _load_handler()
    monkeypatch.setenv("CONTENT_AGENT_WORKSPACE", str(tmp_path))
    _seed_workspace(tmp_path, "ws2", {
        "type": "document", "meta": {"title": "T"},
        "children": [{"type": "paragraph", "id": "p1", "text": "BP cuff size matters"}],
        "attributions": [{"node_id": "p1", "document_id": "d"}],
    })

    class FakeProvider:
        async def embed_batch(self, texts):
            # Identical-direction vectors → cosine ≈ 1
            return [[0.7, 0.7, 0.0], [0.7, 0.7, 0.0]]

    async def _run():
        with patch.object(mod, "get_embedding_provider", return_value=FakeProvider()):
            with patch.object(mod, "_get_source_excerpt", new=AsyncMock(return_value="Use the correct BP cuff size")):
                with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                    from prisma import Prisma
                    with patch.object(Prisma, "connect", new=AsyncMock(return_value=None)):
                        with patch.object(Prisma, "disconnect", new=AsyncMock(return_value=None)):
                            return await mod.execute(inputs={"workspace_id": "ws2"})

    r = asyncio.run(_run())
    assert r["per_node"][0]["supported"] is True
    assert r["per_node"][0]["similarity"] > 0.95
    assert r["unsupported_count"] == 0


def test_cosine_edge_cases():
    mod = _load_handler()
    assert mod._cosine([], [1.0]) == 0.0
    assert mod._cosine([1.0, 0.0], [0.0, 0.0]) == 0.0
    assert abs(mod._cosine([1.0, 0.0], [1.0, 0.0]) - 1.0) < 1e-9
    assert abs(mod._cosine([1.0, 0.0], [-1.0, 0.0]) + 1.0) < 1e-9
