"""Integration test for the generate-docx-blocks handler (Phase 10B)."""
from __future__ import annotations

import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from docx import Document
from prisma import Prisma


@pytest.fixture
async def seeded_source_doc():
    db = Prisma()
    await db.connect()
    try:
        d = await db.document.create(data={
            "title": "Test Source",
            "summary": "Stub summary",
            "topics": ["t1", "t2"],
        })
        chap = await db.chapter.create(data={
            "documentId": d.id, "title": "C1", "orderIndex": 0, "summary": "ch sum",
        })
        await db.section.create(data={
            "chapterId": chap.id, "title": "S1", "orderIndex": 0, "summary": "sec sum",
        })
        yield d.id
        await db.document.delete(where={"id": d.id})
    finally:
        await db.disconnect()


@pytest.mark.asyncio
async def test_handler_produces_real_docx_bytes(seeded_source_doc):
    from officeplane.content_agent.skill_executor import SkillExecutor

    ex = SkillExecutor()

    fake_blocks = {
        "schema_version": "1.0",
        "title": "Generated Brief",
        "modules": [{
            "id": "m1",
            "title": "Overview",
            "lessons": [{
                "id": "l1",
                "title": "Key Points",
                "order": 0,
                "blocks": [
                    {"type": "title", "content": "Background", "order": 0},
                    {"type": "text", "content": "Background prose.", "order": 1, "source_references": [
                        {"document_id": seeded_source_doc, "document_title": "Test Source"}
                    ]},
                ],
            }],
        }],
    }
    fake_response = MagicMock()
    fake_response.choices = [MagicMock(message=MagicMock(content=json.dumps(fake_blocks)))]

    # Patch litellm at the top-level module so the dynamically-loaded handler.py
    # (which does `import litellm`) picks up the mock regardless of load path.
    with patch(
        "litellm.acompletion",
        new=AsyncMock(return_value=fake_response),
    ):
        with patch(
            "officeplane.content_agent.skill_executor.SkillExecutor._emit_audit",
            new=AsyncMock(),
        ):
            output = await ex.invoke(
                "generate-docx-blocks",
                {
                    "source_document_ids": [seeded_source_doc],
                    "brief": "1-page summary for new hires",
                    "target_length": "short",
                },
            )

    assert output["blocks_count"] == 2
    assert output["title"] == "Generated Brief"
    assert seeded_source_doc in output["source_document_ids"]

    from pathlib import Path
    blob = Path(output["file_path"]).read_bytes()
    assert blob.startswith(b"PK")
    parsed = Document(io.BytesIO(blob))
    all_headings = [
        p.text for p in parsed.paragraphs
        if p.style.name.startswith("Heading") or p.style.name == "Title"
    ]
    assert "Generated Brief" in all_headings
