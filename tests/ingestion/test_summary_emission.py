"""Phase 1.3 — summary emission through the ingestion pipeline."""
from __future__ import annotations

import pytest

from officeplane.ingestion.structure_parser import parse_vision_response
from officeplane.ingestion.vision_adapters.mock import (
    MockVisionAdapter,
    create_mock_response,
)


def test_parser_extracts_document_summary():
    raw = {
        "title": "Doc",
        "document_summary": "An overview.",
        "topics": ["x", "y"],
        "key_entities": {"people": ["A"]},
        "chapters": [
            {
                "title": "C",
                "order": 0,
                "summary": "chap sum",
                "sections": [
                    {
                        "title": "S",
                        "order": 0,
                        "summary": "sec sum",
                        "pages": [{"page_number": 1, "content": "page text"}],
                    }
                ],
            }
        ],
    }
    result = parse_vision_response(raw)
    assert result.success
    doc = result.document
    assert doc.summary == "An overview."
    assert doc.topics == ["x", "y"]
    assert doc.key_entities == {"people": ["A"]}
    assert doc.chapters[0].summary == "chap sum"
    assert doc.chapters[0].sections[0].summary == "sec sum"


def test_parser_handles_missing_summary_fields():
    raw = create_mock_response()  # no canned summary
    result = parse_vision_response(raw)
    assert result.success
    doc = result.document
    assert doc.summary is None
    assert doc.topics == []
    assert doc.key_entities == {}


def test_mock_adapter_canned_fields_propagate():
    """MockVisionAdapter with canned args emits them in the response dict."""
    adapter = MockVisionAdapter(
        canned_summary="Mock overview.",
        canned_topics=["ai", "ethics"],
        canned_key_entities={"orgs": ["NIST"]},
    )
    # Directly call _generate_default_response to inspect the dict
    response = adapter._generate_default_response(2)
    assert response["document_summary"] == "Mock overview."
    assert response["topics"] == ["ai", "ethics"]
    assert response["key_entities"] == {"orgs": ["NIST"]}


def test_create_mock_response_canned_fields():
    """create_mock_response helper injects canned summary fields."""
    raw = create_mock_response(
        canned_summary="Canned overview.",
        canned_topics=["topic-a"],
        canned_key_entities={"places": ["London"]},
    )
    result = parse_vision_response(raw)
    assert result.success
    doc = result.document
    assert doc.summary == "Canned overview."
    assert doc.topics == ["topic-a"]
    assert doc.key_entities == {"places": ["London"]}


def test_section_summary_flows_from_mock():
    """Section summary from mock response is captured by the parser."""
    raw = create_mock_response()
    result = parse_vision_response(raw)
    assert result.success
    # Default mock response includes section summaries
    section = result.document.chapters[0].sections[0]
    assert section.summary == "section summary 1"


@pytest.mark.asyncio
async def test_store_persists_document_summary():
    """End-to-end: store layer round-trips summary fields."""
    from officeplane.documents.store import DocumentStore

    store = DocumentStore()
    await store.connect()
    doc = None
    try:
        doc = await store.create_document(
            title="Persist Test",
            summary="Persisted overview.",
            topics=["alpha", "beta"],
            key_entities={"orgs": ["Acme"]},
        )
        assert doc.summary == "Persisted overview."
        assert doc.topics == ["alpha", "beta"]
        assert doc.key_entities == {"orgs": ["Acme"]}

        # Read back via get_document
        fetched = await store.get_document(doc.id)
        assert fetched is not None
        assert fetched.summary == "Persisted overview."
        assert fetched.topics == ["alpha", "beta"]
        assert fetched.key_entities == {"orgs": ["Acme"]}
    finally:
        if doc is not None:
            await store.delete_document(doc.id)
        await store.close()


@pytest.mark.asyncio
async def test_store_persists_section_summary():
    """End-to-end: store layer round-trips section summary."""
    from officeplane.documents.store import DocumentStore

    store = DocumentStore()
    await store.connect()
    doc = None
    try:
        doc = await store.create_document(title="Section Summary Test")
        chapter = await store.create_chapter(
            document_id=doc.id,
            title="Chapter 1",
            order_index=0,
        )
        section = await store.create_section(
            chapter_id=chapter.id,
            title="Section 1",
            order_index=0,
            summary="Section overview text.",
        )
        assert section.summary == "Section overview text."

        # Read back
        fetched = await store.get_section(section.id)
        assert fetched is not None
        assert fetched.summary == "Section overview text."
    finally:
        if doc is not None:
            await store.delete_document(doc.id)
        await store.close()
