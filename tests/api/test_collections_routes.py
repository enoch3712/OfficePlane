"""Tests for the real-DB collections routes (Phase 8.1)."""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_create_then_get_collection():
    from officeplane.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        created = await ac.post(
            "/api/ecm/collections",
            json={"name": "Phase8 Test Coll", "description": "fixture"},
        )
        assert created.status_code == 201
        cid = created.json()["collection_id"]

        fetched = await ac.get(f"/api/ecm/collections/{cid}")
        assert fetched.status_code == 200
        body = fetched.json()
        assert body["name"] == "Phase8 Test Coll"
        assert body["document_count"] == 0
        assert body["child_count"] == 0

        # cleanup
        await ac.delete(f"/api/ecm/collections/{cid}")


@pytest.mark.asyncio
async def test_get_unknown_collection_returns_404():
    import uuid
    from officeplane.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        r = await ac.get(f"/api/ecm/collections/{uuid.uuid4()}")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_nested_collections_parent_id():
    from officeplane.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        parent = (await ac.post("/api/ecm/collections", json={"name": "P-parent"})).json()
        child = (await ac.post(
            "/api/ecm/collections",
            json={"name": "P-child", "parent_id": parent["collection_id"]},
        )).json()

        listed = await ac.get(f"/api/ecm/collections?parent_id={parent['collection_id']}")
        names = [c["name"] for c in listed.json()["collections"]]
        assert "P-child" in names

        await ac.delete(f"/api/ecm/collections/{child['collection_id']}")
        await ac.delete(f"/api/ecm/collections/{parent['collection_id']}")


@pytest.mark.asyncio
async def test_add_document_to_collection_round_trip():
    """Create coll, create doc, link, list, unlink."""
    from officeplane.api.main import app
    from prisma import Prisma

    db = Prisma()
    await db.connect()
    doc = await db.document.create(data={"title": "Phase8 doc"})
    await db.disconnect()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        coll = (await ac.post("/api/ecm/collections", json={"name": "Phase8 link"})).json()
        cid = coll["collection_id"]

        link = await ac.post(
            f"/api/ecm/collections/{cid}/documents",
            json={"document_id": str(doc.id)},
        )
        assert link.status_code == 201

        listed = await ac.get(f"/api/ecm/collections/{cid}/documents")
        body = listed.json()
        assert body["total"] == 1
        assert body["documents"][0]["title"] == "Phase8 doc"

        unlink = await ac.delete(
            f"/api/ecm/collections/{cid}/documents/{doc.id}"
        )
        assert unlink.status_code == 204

        await ac.delete(f"/api/ecm/collections/{cid}")

    db = Prisma()
    await db.connect()
    await db.document.delete(where={"id": doc.id})
    await db.disconnect()
