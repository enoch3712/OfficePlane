import asyncio
import json
import pytest
from unittest.mock import patch, AsyncMock
from officeplane.content_agent.persistence import (
    persist_skill_invocation,
    persist_initial_revision,
    persist_edit_revision,
    persist_derivations_from_document,
    prompt_hash,
    _is_uuid,
)
from officeplane.content_agent.renderers.document import parse_document, Attribution


def test_prompt_hash_deterministic():
    assert prompt_hash("hello") == prompt_hash("hello")
    assert prompt_hash("hello").startswith("sha256:")
    assert prompt_hash("hello") != prompt_hash("world")


def test_is_uuid_filters_garbage():
    import uuid as _u
    good = str(_u.uuid4())
    assert _is_uuid(good)
    assert not _is_uuid("not-a-uuid")
    assert not _is_uuid(None)
    assert not _is_uuid(123)


@pytest.mark.asyncio
async def test_persist_skill_invocation_inserts_row_and_returns_id():
    from prisma import Prisma
    db = Prisma()
    await db.connect()
    try:
        inv_id = await persist_skill_invocation(
            skill="test-skill", model="test-model", workspace_id=None,
            inputs={"x": 1}, outputs={"y": 2}, status="ok", error_message=None,
            duration_ms=42,
        )
        assert inv_id is not None
        row = await db.skillinvocation.find_unique(where={"id": inv_id})
        assert row.skill == "test-skill"
        assert row.status == "ok"
        await db.skillinvocation.delete(where={"id": inv_id})
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_revisions_form_dag():
    from prisma import Prisma
    import uuid as _u
    db = Prisma()
    await db.connect()
    try:
        ws = str(_u.uuid4())
        r1 = await persist_initial_revision(workspace_id=ws, op="create", payload={"title": "X"})
        r2_id, r2_n = await persist_edit_revision(workspace_id=ws, op="replace", payload={"node_id": "p1"})
        r3_id, r3_n = await persist_edit_revision(workspace_id=ws, op="delete", payload={"target_id": "p2"})
        assert r2_n == 2 and r3_n == 3
        # Walk parents
        cur = await db.documentrevision.find_unique(where={"id": r3_id})
        chain = []
        while cur:
            chain.append(cur.revisionNumber)
            cur = await db.documentrevision.find_unique(where={"id": cur.parentRevisionId}) if cur.parentRevisionId else None
        assert chain == [3, 2, 1]
        await db.documentrevision.delete_many(where={"workspaceId": ws})
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_persist_derivations_with_uuid_filtering():
    from prisma import Prisma
    import uuid as _u
    db = Prisma()
    await db.connect()
    try:
        docs = await db.document.find_many(take=1)
        if not docs:
            pytest.skip("no docs ingested")
        real_doc_id = docs[0].id
        ws = str(_u.uuid4())
        doc = parse_document({"type": "document", "meta": {"title": "T"},
            "children": [{"type": "paragraph", "id": "p1", "text": "x"}],
            "attributions": [
                {"node_id": "p1", "document_id": real_doc_id, "section_id": "not-a-uuid"},
                {"node_id": "p2", "document_id": "bogus", "section_id": str(_u.uuid4())},
            ],
        })
        n = await persist_derivations_from_document(
            workspace_id=ws, generated_doc_path="/data/workspaces/x/output.docx",
            doc=doc, skill="generate-docx", model="m", prompt="p",
        )
        assert n == 2
        rows = await db.derivation.find_many(where={"workspaceId": ws})
        assert len(rows) == 2
        # First row has valid source_document_id; second has it nulled (UUID filter)
        by_node = {r.generatedNodeId: r for r in rows}
        assert by_node["p1"].sourceDocumentId == real_doc_id
        assert by_node["p2"].sourceDocumentId is None
        await db.derivation.delete_many(where={"workspaceId": ws})
    finally:
        await db.disconnect()
