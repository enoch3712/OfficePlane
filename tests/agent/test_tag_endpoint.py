import asyncio
import uuid

import pytest
from fastapi.testclient import TestClient


def _client():
    from officeplane.api.main import app
    return TestClient(app)


def test_create_tag_validates_name():
    c = _client()
    for bad in ["Invalid Caps", "with spaces", "has_underscore", "@symbol", "x" * 60]:
        r = c.post("/api/tags", json={"name": bad})
        assert r.status_code == 422 or r.status_code == 400, f"expected validation error for {bad!r}, got {r.status_code}"


def test_create_tag_and_list():
    c = _client()
    name = f"test-{uuid.uuid4().hex[:8]}"
    r = c.post("/api/tags", json={"name": name, "color": "#FF00AA"})
    assert r.status_code == 201
    body = r.json()
    assert body["name"] == name
    assert body["created"] is True
    tag_id = body["id"]

    # Listing returns it
    lst = c.get("/api/tags")
    assert lst.status_code == 200
    names = [t["name"] for t in lst.json()["tags"]]
    assert name in names

    # Search filter
    q = c.get(f"/api/tags?q={name[:4]}")
    assert q.status_code == 200
    assert any(t["name"] == name for t in q.json()["tags"])

    # Idempotent create
    r2 = c.post("/api/tags", json={"name": name})
    assert r2.status_code == 201
    assert r2.json()["created"] is False
    assert r2.json()["id"] == tag_id

    # Cleanup
    c.delete(f"/api/tags/{tag_id}")


def test_add_remove_document_tag():
    """Use the well-known BP doc if present; skip otherwise."""
    BP = "d0a5322e-e48b-4fcc-974c-cc246fcac65b"
    c = _client()
    # Verify the document exists
    check = c.get(f"/api/documents/{BP}/tags")
    if check.status_code == 404:
        pytest.skip("BP doc not present")
    doc_id = BP
    name = f"smoke-{uuid.uuid4().hex[:6]}"

    add = c.post(f"/api/documents/{doc_id}/tags", json={"tag_name": name, "actor": "test"})
    assert add.status_code == 201
    assert add.json()["added"] is True

    # Idempotent add
    add2 = c.post(f"/api/documents/{doc_id}/tags", json={"tag_name": name})
    assert add2.status_code == 201
    assert add2.json()["added"] is False

    # Get
    g = c.get(f"/api/documents/{doc_id}/tags")
    assert g.status_code == 200
    assert any(t["name"] == name for t in g.json()["tags"])

    # Cross-listing
    by_tag = c.get(f"/api/tags/{name}/documents")
    assert by_tag.status_code == 200
    assert any(d["id"] == doc_id for d in by_tag.json()["documents"])

    # Remove
    rm = c.delete(f"/api/documents/{doc_id}/tags/{name}")
    assert rm.status_code == 200

    # Now empty
    g2 = c.get(f"/api/documents/{doc_id}/tags")
    assert all(t["name"] != name for t in g2.json()["tags"])

    # Cleanup the tag itself
    tag_id_list = c.get(f"/api/tags?q={name}").json()["tags"]
    if tag_id_list:
        c.delete(f"/api/tags/{tag_id_list[0]['id']}")


def test_remove_nonexistent_tag_404():
    """Tag not found returns 404 — use a well-known doc UUID to avoid /api/documents call."""
    c = _client()
    # Any existing doc — use the well-known BP doc if present, else any UUID (tag not found comes first)
    bp_doc = "d0a5322e-e48b-4fcc-974c-cc246fcac65b"
    r = c.delete(f"/api/documents/{bp_doc}/tags/never-existed-tag-zzz")
    # Either 404 (tag not found) or 404 (doc not found) — both are correct 404s
    assert r.status_code == 404


def test_document_not_found_returns_404():
    c = _client()
    r = c.get(f"/api/documents/{uuid.uuid4()}/tags")
    assert r.status_code == 404


def test_invalid_tag_name_on_add():
    BP = "d0a5322e-e48b-4fcc-974c-cc246fcac65b"
    c = _client()
    check = c.get(f"/api/documents/{BP}/tags")
    if check.status_code == 404:
        pytest.skip("BP doc not present")
    r = c.post(f"/api/documents/{BP}/tags", json={"tag_name": "INVALID NAME"})
    assert r.status_code == 400
