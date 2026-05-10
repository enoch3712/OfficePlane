import pytest
from prisma import Json, Prisma

@pytest.mark.asyncio
async def test_document_summary_round_trip():
    db = Prisma()
    await db.connect()
    try:
        doc = await db.document.create(
            data={
                "title": "Summary Test",
                "summary": "Top-level overview.",
                "topics": ["ai", "ethics"],
                "keyEntities": Json({"people": ["Alice"], "orgs": ["Acme"]}),
            }
        )
        assert doc.summary == "Top-level overview."
        assert doc.topics == ["ai", "ethics"]
        assert doc.keyEntities["people"] == ["Alice"]

        sec_doc = await db.document.create(data={"title": "Sec parent"})
        chap = await db.chapter.create(
            data={"documentId": sec_doc.id, "title": "C1", "orderIndex": 0, "summary": "chap summary"}
        )
        sec = await db.section.create(
            data={"chapterId": chap.id, "title": "S1", "orderIndex": 0, "summary": "sec summary"}
        )
        assert sec.summary == "sec summary"
    finally:
        await db.disconnect()
