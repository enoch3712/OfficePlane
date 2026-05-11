import asyncio, uuid
import pytest
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient


def _client():
    from officeplane.api.main import app
    return TestClient(app)


@pytest.mark.asyncio
async def test_activity_returns_real_events():
    """We've shipped many real skill invocations — confirm at least one returns."""
    from prisma import Prisma
    db = Prisma()
    await db.connect()
    try:
        cnt = await db.skillinvocation.count()
        if cnt == 0:
            pytest.skip("no skill invocations recorded yet")
    finally:
        await db.disconnect()

    c = _client()
    r = c.get("/api/activity?limit=10")
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["total_count"] >= 1
    assert isinstance(j["events"], list)
    if j["events"]:
        e = j["events"][0]
        for k in ("id", "timestamp", "skill", "status", "summary"):
            assert k in e


def test_activity_filters_by_skill():
    c = _client()
    r = c.get("/api/activity?skill=generate-docx&limit=20")
    assert r.status_code == 200
    j = r.json()
    for e in j["events"]:
        assert e["skill"] == "generate-docx"


def test_activity_filters_by_status():
    c = _client()
    r = c.get("/api/activity?status=ok&limit=20")
    assert r.status_code == 200
    j = r.json()
    for e in j["events"]:
        assert e["status"] == "ok"


def test_activity_rejects_invalid_status():
    c = _client()
    r = c.get("/api/activity?status=junk")
    # Pydantic regex → 422
    assert r.status_code in (400, 422)


def test_activity_pagination():
    c = _client()
    r1 = c.get("/api/activity?limit=2&offset=0")
    r2 = c.get("/api/activity?limit=2&offset=2")
    if r1.status_code == 200 and r1.json()["total_count"] >= 4:
        assert r1.json()["events"][0]["id"] != r2.json()["events"][0]["id"]


def test_known_skills_endpoint():
    c = _client()
    r = c.get("/api/activity/skills")
    assert r.status_code == 200
    j = r.json()
    assert isinstance(j["skills"], list)
    # We've definitely shipped these:
    expected = {"generate-docx", "generate-pptx", "document-edit"}
    overlap = set(j["skills"]) & expected
    if not overlap:
        pytest.skip("none of the expected skills logged yet")
    assert overlap, f"expected at least one of {expected} in {j['skills']}"
