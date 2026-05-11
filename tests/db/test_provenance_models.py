import asyncio
import json
import pytest
from prisma import Prisma


@pytest.mark.asyncio
async def test_derivation_insert_and_query():
    db = Prisma()
    await db.connect()
    try:
        # Use the already-ingested document if present, else skip
        docs = await db.document.find_many(take=1)
        if not docs:
            pytest.skip("no documents ingested")
        src_doc = docs[0]
        import uuid as _u
        ws_id = str(_u.uuid4())
        d = await db.derivation.create(data={
            "workspaceId": ws_id,
            "generatedNodeId": "p7",
            "sourceDocumentId": src_doc.id,
            "skill": "generate-docx",
            "model": "deepseek/deepseek-v4-flash",
            "promptHash": "sha256:" + "0" * 64,
            "confidence": 0.85,
            "pageNumbers": [4, 5],
            "textExcerpt": "BP measurement matters.",
        })
        fetched = await db.derivation.find_unique(where={"id": d.id})
        assert fetched.generatedNodeId == "p7"
        assert fetched.sourceDocumentId == src_doc.id
        assert fetched.pageNumbers == [4, 5]
        await db.derivation.delete(where={"id": d.id})
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_document_revision_dag():
    db = Prisma()
    await db.connect()
    try:
        import uuid as _u
        ws_id = str(_u.uuid4())
        r1 = await db.documentrevision.create(data={
            "workspaceId": ws_id,
            "revisionNumber": 1,
            "op": "create",
            "payload": json.dumps({"title": "Initial"}),
            "actor": "system",
        })
        r2 = await db.documentrevision.create(data={
            "workspaceId": ws_id,
            "parentRevisionId": r1.id,
            "revisionNumber": 2,
            "op": "insert_after",
            "payload": json.dumps({"anchor_id": "p1", "node_id": "p1.5"}),
            "actor": "user-abc",
        })
        assert r2.parentRevisionId == r1.id
        # Walk parent chain
        cur = r2
        chain = []
        while cur:
            chain.append(cur.revisionNumber)
            cur = await db.documentrevision.find_unique(where={"id": cur.parentRevisionId}) if cur.parentRevisionId else None
        assert chain == [2, 1]
        await db.documentrevision.delete_many(where={"workspaceId": ws_id})
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_skill_invocation_log():
    db = Prisma()
    await db.connect()
    try:
        inv = await db.skillinvocation.create(data={
            "skill": "generate-docx",
            "model": "deepseek/deepseek-v4-flash",
            "inputs": json.dumps({"brief": "test"}),
            "outputs": json.dumps({"file_path": "/data/...", "node_count": 12}),
            "status": "ok",
            "durationMs": 4200,
        })
        assert inv.skill == "generate-docx"
        assert inv.status == "ok"
        await db.skillinvocation.delete(where={"id": inv.id})
    finally:
        await db.disconnect()
