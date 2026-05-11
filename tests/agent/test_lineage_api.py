import json
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timezone
from fastapi.testclient import TestClient


def _client():
    from officeplane.api.main import app
    return TestClient(app)


def _ts():
    return datetime.now(tz=timezone.utc)


def test_lineage_404_when_document_missing():
    c = _client()
    r = c.get("/api/documents/00000000-0000-0000-0000-000000000000/lineage")
    assert r.status_code == 404
    assert "not found" in r.json()["detail"].lower()


def test_lineage_returns_empty_arrays_when_no_derivations(monkeypatch):
    c = _client()
    # Find a real document with no derivations
    import asyncio
    from prisma import Prisma

    async def find_doc():
        db = Prisma()
        await db.connect()
        try:
            docs = await db.document.find_many(take=10)
            for d in docs:
                cnt = await db.derivation.count(where={"sourceDocumentId": d.id})
                if cnt == 0:
                    return d.id
            return None
        finally:
            await db.disconnect()

    doc_id = asyncio.run(find_doc())
    if doc_id is None:
        pytest.skip("every document has derivations — can't test empty path")
    r = c.get(f"/api/documents/{doc_id}/lineage")
    assert r.status_code == 200
    j = r.json()
    assert j["derivations"] == []
    assert j["revisions"] == []
    assert j["nodes"] == []
    assert j["document"]["id"] == doc_id
    assert isinstance(j["sources"], list) and len(j["sources"]) == 1


def test_lineage_returns_real_derivations_and_revisions_for_bp():
    """BP doc was ingested as d0a5322e and has had generate-docx run against it."""
    c = _client()
    BP = "d0a5322e-e48b-4fcc-974c-cc246fcac65b"
    r = c.get(f"/api/documents/{BP}/lineage")
    if r.status_code == 404:
        pytest.skip("BP doc not ingested")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["document"]["title"] == "Measuring Blood Pressure Checklist"
    # At least one derivation expected (assuming Phase 12.2 smoke ran)
    if not j["derivations"]:
        pytest.skip("no derivations yet — run generate-docx against BP first")
    d = j["derivations"][0]
    assert d["source_document_id"] == BP
    assert "generated_node_id" in d and "skill" in d
    assert j["revisions"], "expected at least one revision row"
    assert j["revisions"][0]["op"] in ("create", "regenerate")


def test_lineage_response_shape_keys_snake_case():
    """Ensure the response uses snake_case keys (UI is locked to this)."""
    c = _client()
    BP = "d0a5322e-e48b-4fcc-974c-cc246fcac65b"
    r = c.get(f"/api/documents/{BP}/lineage")
    if r.status_code != 200:
        pytest.skip("BP doc missing or has no derivations")
    j = r.json()
    # Top-level keys
    for k in ("document", "nodes", "sources", "derivations", "revisions"):
        assert k in j
    # Document shape
    for k in ("id", "title", "workspace_id", "output_path"):
        assert k in j["document"]
    # Derivation shape (if any)
    if j["derivations"]:
        for k in ("id", "generated_node_id", "source_document_id", "page_numbers",
                  "skill", "model", "created_at"):
            assert k in j["derivations"][0]
    # Revision shape
    if j["revisions"]:
        for k in ("id", "parent_revision_id", "revision_number", "op", "payload", "created_at"):
            assert k in j["revisions"][0]
