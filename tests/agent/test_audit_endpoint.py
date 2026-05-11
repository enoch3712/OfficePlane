"""Tests for the real audit endpoint backed by skill_invocations table."""
import pytest
from fastapi.testclient import TestClient


def _client():
    from officeplane.api.main import app
    return TestClient(app)


def test_audit_404_when_document_missing():
    c = _client()
    r = c.get("/api/ecm/documents/00000000-0000-0000-0000-000000000000/audit")
    assert r.status_code == 404


def test_audit_returns_real_bp_events():
    """BP doc has had generate-docx run against it multiple times."""
    BP = "d0a5322e-e48b-4fcc-974c-cc246fcac65b"
    c = _client()
    r = c.get(f"/api/ecm/documents/{BP}/audit")
    if r.status_code == 404:
        pytest.skip("BP doc not ingested")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["document_id"] == BP
    assert isinstance(j["total_count"], int)
    if j["total_count"] == 0:
        pytest.skip("no invocations yet")
    e = j["events"][0]
    for k in ("id", "timestamp", "skill", "status", "summary"):
        assert k in e
    assert isinstance(e["skill"], str) and e["skill"]  # any valid skill name


def test_audit_pagination():
    BP = "d0a5322e-e48b-4fcc-974c-cc246fcac65b"
    c = _client()
    r1 = c.get(f"/api/ecm/documents/{BP}/audit?limit=2&offset=0")
    if r1.status_code != 200 or r1.json()["total_count"] < 3:
        pytest.skip("not enough events")
    j1 = r1.json()
    assert len(j1["events"]) <= 2
    r2 = c.get(f"/api/ecm/documents/{BP}/audit?limit=2&offset=2")
    j2 = r2.json()
    # Different page → different first event
    if j2["events"]:
        assert j1["events"][0]["id"] != j2["events"][0]["id"]


def test_audit_summary_strings_meaningful():
    BP = "d0a5322e-e48b-4fcc-974c-cc246fcac65b"
    c = _client()
    r = c.get(f"/api/ecm/documents/{BP}/audit")
    if r.status_code != 200 or not r.json()["events"]:
        pytest.skip("no events")
    summaries = [e["summary"] for e in r.json()["events"]]
    # At least one summary should match expected vocabulary
    assert any("Generated" in s or "Edited" in s or "error" in s.lower() for s in summaries)
