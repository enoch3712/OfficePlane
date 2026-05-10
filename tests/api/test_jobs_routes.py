"""Tests for jobs_routes after the SkillExecutor rewire (Phase 3.4b)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_start_job_unknown_skill_returns_404():
    """Lookup goes through SkillExecutor, not the legacy registry."""
    from officeplane.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/jobs",
            json={"skill": "absolutely-not-a-real-skill", "prompt": "hi"},
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_invoke_skill_sync_unknown_returns_404():
    from officeplane.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.post(
            "/api/jobs/invoke/no-such-skill",
            json={"inputs": {}},
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_invoke_skill_sync_input_error_returns_400():
    """Missing required input -> 400."""
    from officeplane.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # document-search requires `query`; sending empty inputs should 400.
        r = await ac.post(
            "/api/jobs/invoke/document-search",
            json={"inputs": {}},
        )
    assert r.status_code == 400
    assert "query" in r.text


@pytest.mark.asyncio
async def test_invoke_skill_sync_dispatches_through_executor():
    """Happy path: the LLM call is mocked, executor returns the parsed output, route returns it."""
    from officeplane.api.main import app
    from officeplane.api import jobs_routes

    fake_output = {"results": [{"title": "Doc"}]}

    transport = ASGITransport(app=app)
    with patch.object(
        jobs_routes._executor,
        "invoke",
        new=AsyncMock(return_value=fake_output),
    ):
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            r = await ac.post(
                "/api/jobs/invoke/document-search",
                json={"inputs": {"query": "hello"}},
            )

    assert r.status_code == 200
    body = r.json()
    assert body["skill"] == "document-search"
    assert body["output"] == fake_output
