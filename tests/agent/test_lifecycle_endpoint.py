import asyncio
import uuid
import pytest
from fastapi.testclient import TestClient


def _client():
    from officeplane.api.main import app
    return TestClient(app)


@pytest.mark.asyncio
async def test_transitions_and_history():
    from prisma import Prisma
    db = Prisma()
    await db.connect()
    try:
        docs = await db.document.find_many(take=1)
        if not docs:
            pytest.skip("no documents ingested")
        doc_id = docs[0].id
        c = _client()
        # Reset to DRAFT for a clean test path
        await db.document.update(where={"id": doc_id}, data={"status": "DRAFT"})

        # DRAFT → REVIEW (allowed)
        r = c.post(f"/api/documents/{doc_id}/transition",
                   json={"to_status": "REVIEW", "actor": "test", "note": "ready for review"})
        assert r.status_code == 200, r.text
        j = r.json()
        assert j["from_status"] == "DRAFT" and j["to_status"] == "REVIEW"

        # REVIEW → APPROVED (allowed)
        r = c.post(f"/api/documents/{doc_id}/transition",
                   json={"to_status": "APPROVED", "actor": "qa"})
        assert r.status_code == 200

        # APPROVED → DRAFT (not allowed)
        r = c.post(f"/api/documents/{doc_id}/transition", json={"to_status": "DRAFT"})
        assert r.status_code == 400
        assert "not allowed" in r.json()["detail"]

        # History
        h = c.get(f"/api/documents/{doc_id}/status-history")
        assert h.status_code == 200
        assert h.json()["current_status"] == "APPROVED"
        assert len(h.json()["events"]) >= 2

        # Cleanup — back to DRAFT (via REVIEW first, since APPROVED → DRAFT isn't allowed)
        await db.document.update(where={"id": doc_id}, data={"status": "DRAFT"})
    finally:
        await db.disconnect()


def test_transition_404_on_missing_doc():
    c = _client()
    r = c.post(f"/api/documents/{uuid.uuid4()}/transition", json={"to_status": "REVIEW"})
    assert r.status_code == 404


def test_history_404_on_missing_doc():
    c = _client()
    r = c.get(f"/api/documents/{uuid.uuid4()}/status-history")
    assert r.status_code == 404


def test_transition_validates_target_enum():
    c = _client()
    r = c.post("/api/documents/00000000-0000-0000-0000-000000000000/transition",
               json={"to_status": "INVALID"})
    # FastAPI's pydantic Literal validation → 422
    assert r.status_code in (422, 400)


def test_archived_is_terminal():
    """ARCHIVED has no outgoing transitions — empty set."""
    from officeplane.api.lifecycle_routes import TRANSITIONS
    assert TRANSITIONS["ARCHIVED"] == set()
    assert "REVIEW" in TRANSITIONS["DRAFT"]
    assert "APPROVED" in TRANSITIONS["REVIEW"]
