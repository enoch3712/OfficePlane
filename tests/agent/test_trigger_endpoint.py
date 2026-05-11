import json
import uuid
import pytest
from fastapi.testclient import TestClient


def _client():
    from officeplane.api.main import app
    return TestClient(app)


def test_crud_trigger_lifecycle():
    c = _client()
    body = {
        "name": f"smoke-{uuid.uuid4().hex[:6]}",
        "event_type": "document.uploaded",
        "filter": {"==": [{"var": "document.source_format"}, "pdf"]},
        "pipeline_spec": {"name": "noop", "steps": [{"skill": "noop", "inputs": {}}]},
        "status": "ENABLED",
    }
    r = c.post("/api/triggers", json=body)
    assert r.status_code == 201, r.text
    tid = r.json()["id"]

    g = c.get(f"/api/triggers/{tid}")
    assert g.status_code == 200
    assert g.json()["event_type"] == "document.uploaded"
    assert g.json()["filter"] == body["filter"]

    p = c.patch(f"/api/triggers/{tid}", json={"status": "DISABLED"})
    assert p.status_code == 200
    assert p.json()["status"] == "DISABLED"

    lst = c.get("/api/triggers?event_type=document.uploaded")
    assert lst.status_code == 200
    assert any(t["id"] == tid for t in lst.json()["triggers"])

    d = c.delete(f"/api/triggers/{tid}")
    assert d.status_code == 200


def test_invalid_pipeline_spec_rejected():
    c = _client()
    body = {
        "name": "bad", "event_type": "x",
        "filter": {}, "pipeline_spec": {"steps": []},  # empty steps
    }
    r = c.post("/api/triggers", json=body)
    assert r.status_code == 400


def test_test_filter_endpoint():
    c = _client()
    rule = {"==": [{"var": "x"}, 1]}
    r = c.post("/api/triggers/test-filter", json={"filter": rule, "payload": {"x": 1}})
    assert r.status_code == 200
    assert r.json()["matched"] is True
    r2 = c.post("/api/triggers/test-filter", json={"filter": rule, "payload": {"x": 2}})
    assert r2.json()["matched"] is False


def test_emit_event_endpoint():
    c = _client()
    r = c.post("/api/events/emit", json={"event_type": "debug.smoke", "payload": {"a": 1}})
    assert r.status_code == 200
    eid = r.json()["event_id"]

    events = c.get("/api/events?event_type=debug.smoke&limit=5")
    assert events.status_code == 200
    assert any(e["id"] == eid for e in events.json()["events"])
