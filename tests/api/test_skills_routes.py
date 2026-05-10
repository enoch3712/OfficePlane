"""Tests for the merged skills_routes (Phase 3.4c)."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_list_skills_includes_skill_md():
    from officeplane.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/skills")
    assert r.status_code == 200
    names = {s["name"] for s in r.json()["skills"]}
    # At least one of our 12 ECM skills must be present
    assert "audit-query" in names
    assert "document-search" in names


@pytest.mark.asyncio
async def test_get_skill_resolves_skill_md_first():
    from officeplane.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/skills/document-search")
    assert r.status_code == 200
    assert r.json()["source"] == "skill_md"


@pytest.mark.asyncio
async def test_get_unknown_skill_returns_404():
    from officeplane.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get("/api/skills/totally-not-real")
    assert r.status_code == 404
