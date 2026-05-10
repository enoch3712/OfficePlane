"""Tests for batch upload to a collection (Phase 8.2)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


@pytest.mark.asyncio
async def test_batch_upload_routes_each_file_through_ingest():
    from officeplane.api.main import app

    fake_doc = {"id": "abcd-1234", "title": "Doc"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        coll = (await ac.post("/api/ecm/collections", json={"name": "P82 Coll"})).json()
        cid = coll["collection_id"]

        with patch(
            "officeplane.api.management_routes._ingest_uploaded_file",
            new=AsyncMock(return_value=fake_doc),
        ):
            with patch(
                "officeplane.api.management_routes._link_document_to_collection",
                new=AsyncMock(),
            ):
                files = [
                    ("files", ("a.pdf", b"%PDF-fake", "application/pdf")),
                    ("files", ("b.pdf", b"%PDF-fake-2", "application/pdf")),
                ]
                r = await ac.post(f"/api/ecm/collections/{cid}/upload", files=files)

        assert r.status_code == 201
        body = r.json()
        assert body["collection_id"] == cid
        assert len(body["results"]) == 2
        assert all(item["status"] == "ingested" for item in body["results"])

        await ac.delete(f"/api/ecm/collections/{cid}")


@pytest.mark.asyncio
async def test_batch_upload_unknown_collection_404():
    import uuid
    from officeplane.api.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        files = [("files", ("a.pdf", b"%PDF-fake", "application/pdf"))]
        r = await ac.post(f"/api/ecm/collections/{uuid.uuid4()}/upload", files=files)
    assert r.status_code == 404
