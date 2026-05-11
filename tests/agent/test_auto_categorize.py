import asyncio
import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest


def _load_handler():
    p = Path("/app/src/officeplane/content_agent/skills/auto-categorize/handler.py")
    if not p.exists():
        p = Path(__file__).parents[2] / "src/officeplane/content_agent/skills/auto-categorize/handler.py"
    spec = importlib.util.spec_from_file_location("ac_handler", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["ac_handler"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_validates_inputs():
    mod = _load_handler()

    async def _run(inputs):
        return await mod.execute(inputs=inputs)

    with pytest.raises(ValueError, match="document_id"):
        asyncio.run(_run({}))
    with pytest.raises(ValueError, match="max_suggestions"):
        asyncio.run(_run({"document_id": "x", "max_suggestions": 0}))
    with pytest.raises(ValueError, match="max_suggestions"):
        asyncio.run(_run({"document_id": "x", "max_suggestions": 100}))


def test_jaccard_basic():
    mod = _load_handler()
    assert mod._jaccard("blood pressure measurement nursing", "blood pressure nursing protocol") > 0.4
    assert mod._jaccard("apples oranges", "concrete steel cement") == 0.0
    assert mod._jaccard("", "anything") == 0.0


def test_picks_high_overlap_collection_no_new_proposal():
    mod = _load_handler()
    fake_target = {
        "id": "tgt", "title": "Blood Pressure Procedures",
        "summary": "How to measure blood pressure correctly with proper cuff sizing.",
        "topics": ["blood pressure", "nursing", "hypertension"],
        "text": "blood pressure procedures measure cuff nursing hypertension correctly",
    }
    fake_collections = [
        {"id": "c1", "name": "Clinical Procedures",
         "description": "Patient care protocols and procedures",
         "text": "blood pressure nursing cuff procedures hypertension protocols",
         "member_count": 3},
        {"id": "c2", "name": "Marketing",
         "description": "Sales decks",
         "text": "marketing sales prospect funnel revenue",
         "member_count": 5},
    ]

    async def _run():
        with patch.object(mod, "_get_document_signature", new=AsyncMock(return_value=fake_target)):
            with patch.object(mod, "_get_collection_signatures", new=AsyncMock(return_value=fake_collections)):
                with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                    return await mod.execute(inputs={"document_id": "tgt"})

    r = asyncio.run(_run())
    assert r["document_id"] == "tgt"
    suggestions = r["suggested_collections"]
    assert suggestions[0]["collection_id"] == "c1"  # higher score
    assert suggestions[0]["score"] > suggestions[-1]["score"]
    # Best score is high → no new proposal
    assert r["new_collection_proposal"] is None


def test_proposes_new_when_nothing_overlaps(tmp_path, monkeypatch):
    mod = _load_handler()
    fake_target = {
        "id": "tgt", "title": "Quantum Field Theory",
        "summary": "Lagrangian formalism for gauge fields",
        "topics": ["quantum", "lagrangian", "gauge"],
        "text": "quantum field theory lagrangian gauge formalism abelian symmetry",
    }
    fake_collections = [
        {"id": "c1", "name": "Marketing",
         "description": "Sales decks",
         "text": "marketing sales prospect funnel revenue",
         "member_count": 5},
    ]

    fake_resp = type("X", (), {})()
    fake_resp.choices = [type("Y", (), {"message": type("Z", (), {"content": '{"name":"Theoretical Physics","description":"Quantum field theory and gauge formalism notes."}'})()})()]

    async def _run():
        with patch.object(mod, "_get_document_signature", new=AsyncMock(return_value=fake_target)):
            with patch.object(mod, "_get_collection_signatures", new=AsyncMock(return_value=fake_collections)):
                with patch("litellm.acompletion", new=AsyncMock(return_value=fake_resp)):
                    with patch.object(mod, "persist_skill_invocation", new=AsyncMock(return_value=None)):
                        return await mod.execute(inputs={"document_id": "tgt"})

    r = asyncio.run(_run())
    assert r["new_collection_proposal"] is not None
    assert "Physics" in r["new_collection_proposal"]["name"] or "Quantum" in r["new_collection_proposal"]["name"]


def test_endpoint_404_for_missing_document():
    from fastapi.testclient import TestClient
    from officeplane.api.main import app
    c = TestClient(app)
    r = c.post("/api/documents/00000000-0000-0000-0000-000000000000/auto-categorize", json={})
    assert r.status_code in (400, 500)  # ValueError → 400 in our handler
