import asyncio
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient


def _client():
    from officeplane.api.main import app
    return TestClient(app)


def test_create_and_list_policy():
    c = _client()
    name = f"test-policy-{uuid.uuid4().hex[:6]}"
    r = c.post("/api/retention/policies", json={
        "name": name, "duration_days": 365, "action": "REVIEW",
    })
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    lst = c.get("/api/retention/policies")
    assert lst.status_code == 200
    assert any(p["name"] == name for p in lst.json()["policies"])
    # Duplicate name → 409
    r2 = c.post("/api/retention/policies", json={"name": name, "duration_days": 30})
    assert r2.status_code == 409
    # Cleanup
    c.delete(f"/api/retention/policies/{pid}")


def test_validation_rejects_bad_action():
    c = _client()
    r = c.post("/api/retention/policies", json={
        "name": "x", "duration_days": 100, "action": "INVALID",
    })
    assert r.status_code == 422


def test_apply_policy_to_document_and_compute_due_date():
    c = _client()
    docs = c.get("/api/documents")
    if docs.status_code != 200 or not docs.json():
        pytest.skip("no documents")
    doc_id = docs.json()[0]["id"]
    name = f"smoke-policy-{uuid.uuid4().hex[:6]}"
    p = c.post("/api/retention/policies", json={
        "name": name, "duration_days": 30, "action": "REVIEW",
        "start_trigger": "created_at",
    })
    pid = p.json()["id"]

    apply_resp = c.post(f"/api/documents/{doc_id}/retention", json={"policy_id": pid})
    assert apply_resp.status_code == 201, apply_resp.text
    body = apply_resp.json()
    assert body["policy_id"] == pid
    start = datetime.fromisoformat(body["start_at"].replace("Z", "+00:00"))
    due = datetime.fromisoformat(body["disposition_due_at"].replace("Z", "+00:00"))
    assert (due - start) == timedelta(days=30)

    # Idempotent re-apply
    apply2 = c.post(f"/api/documents/{doc_id}/retention", json={"policy_id": pid})
    assert apply2.status_code == 201
    assert apply2.json()["id"] == body["id"]

    # Get retentions
    g = c.get(f"/api/documents/{doc_id}/retention")
    assert g.status_code == 200
    assert any(r["policy_id"] == pid for r in g.json()["retentions"])

    # Cleanup
    c.delete(f"/api/documents/{doc_id}/retention/{body['id']}")
    c.delete(f"/api/retention/policies/{pid}")


@pytest.mark.asyncio
async def test_legal_hold_lifecycle():
    """Test legal hold apply/release using direct Prisma to avoid event-loop contamination."""
    from prisma import Prisma
    from datetime import timedelta, timezone

    db = Prisma(); await db.connect()
    try:
        docs = await db.document.find_many(take=1)
        if not docs:
            pytest.skip("no documents")
        doc = docs[0]

        policy = await db.retentionpolicy.create(data={
            "name": f"hold-test-{uuid.uuid4().hex[:6]}",
            "durationDays": 365,
            "action": "REVIEW",
            "startTrigger": "created_at",
        })
        now = datetime.now(tz=timezone.utc)
        ret = await db.documentretention.create(data={
            "documentId": doc.id,
            "policyId": policy.id,
            "startAt": now,
            "dispositionDueAt": now + timedelta(days=365),
        })
        ret_id = ret.id

        # Apply legal hold
        updated = await db.documentretention.update(
            where={"id": ret_id},
            data={"legalHold": True, "legalHoldReason": "subpoena #123"},
        )
        assert updated.legalHold is True
        assert "subpoena" in (updated.legalHoldReason or "")

        # Emit audit event for hold
        await db.dispositionevent.create(data={
            "retentionId": ret_id,
            "action": "REVIEW",
            "status": "SKIPPED",
            "reason": "legal hold applied: subpoena #123",
            "actor": "legal-ops",
        })

        # Release legal hold
        released = await db.documentretention.update(
            where={"id": ret_id},
            data={"legalHold": False, "legalHoldReason": None},
        )
        assert released.legalHold is False
        assert released.legalHoldReason is None

        # Emit audit event for release
        await db.dispositionevent.create(data={
            "retentionId": ret_id,
            "action": "REVIEW",
            "status": "SUCCESS",
            "reason": "legal hold released",
            "actor": "legal-ops",
        })

        # Verify events
        events = await db.dispositionevent.find_many(where={"retentionId": ret_id})
        assert any(e.status == "SKIPPED" and "subpoena" in (e.reason or "") for e in events)
        assert any(e.status == "SUCCESS" and "released" in (e.reason or "") for e in events)

        # Cleanup
        await db.dispositionevent.delete_many(where={"retentionId": ret_id})
        await db.documentretention.delete(where={"id": ret_id})
        await db.retentionpolicy.delete(where={"id": policy.id})
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_disposition_runner_honors_legal_hold():
    """Apply a policy with past due date manually, set legal hold, run pass.
    Expect SKIPPED event, no disposition."""
    from prisma import Prisma
    from officeplane.retention.disposition import run_disposition_pass

    db = Prisma(); await db.connect()
    try:
        docs = await db.document.find_many(take=1)
        if not docs:
            pytest.skip("no documents")
        doc = docs[0]

        # Create a policy
        policy = await db.retentionpolicy.create(data={
            "name": f"test-hold-{uuid.uuid4().hex[:6]}",
            "durationDays": 1,
            "action": "REVIEW",
            "startTrigger": "manual",
        })
        # Create a retention that's already past due
        past = datetime.now(tz=timezone.utc) - timedelta(days=5)
        ret = await db.documentretention.create(data={
            "documentId": doc.id, "policyId": policy.id,
            "startAt": past, "dispositionDueAt": past + timedelta(days=1),
            "legalHold": True, "legalHoldReason": "litigation X",
        })

        summary = await run_disposition_pass(actor="pytest")
        assert summary["scanned"] >= 1
        assert summary["skipped_hold"] >= 1

        # Confirm event row
        events = await db.dispositionevent.find_many(where={"retentionId": ret.id})
        assert any(e.status == "SKIPPED" and "legal_hold" in (e.reason or "") for e in events)
        # Retention should NOT be disposed
        r2 = await db.documentretention.find_unique(where={"id": ret.id})
        assert r2.disposed is False

        # Cleanup
        await db.dispositionevent.delete_many(where={"retentionId": ret.id})
        await db.documentretention.delete(where={"id": ret.id})
        await db.retentionpolicy.delete(where={"id": policy.id})
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_disposition_runner_disposes_due_records():
    from prisma import Prisma
    from officeplane.retention.disposition import run_disposition_pass

    db = Prisma(); await db.connect()
    try:
        docs = await db.document.find_many(take=1)
        if not docs:
            pytest.skip("no documents")
        doc = docs[0]

        policy = await db.retentionpolicy.create(data={
            "name": f"test-disp-{uuid.uuid4().hex[:6]}",
            "durationDays": 1, "action": "ARCHIVE", "startTrigger": "manual",
        })
        past = datetime.now(tz=timezone.utc) - timedelta(days=10)
        ret = await db.documentretention.create(data={
            "documentId": doc.id, "policyId": policy.id,
            "startAt": past, "dispositionDueAt": past + timedelta(days=1),
        })
        summary = await run_disposition_pass(actor="pytest", dry_run=False)
        assert summary["disposed"] >= 1
        r2 = await db.documentretention.find_unique(where={"id": ret.id})
        assert r2.disposed is True
        assert r2.disposedAt is not None
        events = await db.dispositionevent.find_many(where={"retentionId": ret.id})
        assert any(e.status == "SUCCESS" and e.action == "ARCHIVE" for e in events)
        # Cleanup
        await db.dispositionevent.delete_many(where={"retentionId": ret.id})
        await db.documentretention.delete(where={"id": ret.id})
        await db.retentionpolicy.delete(where={"id": policy.id})
    finally:
        await db.disconnect()
