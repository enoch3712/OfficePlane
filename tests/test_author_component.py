"""
Tests for AuthorComponent.

These tests cover the document authoring functionality including
document creation, chapter/section/page management, and search.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from officeplane.components.author import AuthorComponent
from officeplane.components.context import ComponentContext
from officeplane.documents.models import (
    DocumentModel,
    ChapterModel,
    SectionModel,
    PageModel,
    DocumentOutline,
    ChapterOutline,
    SectionOutline,
    PageOutline,
    PageLocation,
    SearchHit,
)


@pytest.fixture
def mock_doc_store():
    """Create a mock DocumentStore."""
    store = AsyncMock()
    return store


@pytest.fixture
def mock_vector_store():
    """Create a mock VectorStore."""
    store = AsyncMock()
    return store


@pytest.fixture
def mock_embedding_client():
    """Create a mock EmbeddingClient."""
    client = MagicMock()
    client.aembed = AsyncMock(return_value=[0.1] * 1536)
    client.aembed_batch = AsyncMock(return_value=[[0.1] * 1536])
    return client


@pytest.fixture
def ctx():
    """Create a test ComponentContext."""
    mock_driver = MagicMock()
    mock_store = MagicMock()
    return ComponentContext.create(driver=mock_driver, store=mock_store)


@pytest.fixture
def author_component(mock_doc_store, mock_vector_store, mock_embedding_client):
    """Create an AuthorComponent with mocked dependencies."""
    component = AuthorComponent(
        doc_store=mock_doc_store,
        vector_store=mock_vector_store,
        embedding_client=mock_embedding_client,
    )
    # Mark as connected to avoid connection attempts
    component._connected = True
    component._indexer = AsyncMock()
    component._retriever = AsyncMock()
    return component


class TestAuthorComponentInit:
    """Test AuthorComponent initialization."""

    def test_component_name(self):
        """Test component has correct name."""
        author = AuthorComponent()
        assert author.name == "author"

    def test_component_purpose(self):
        """Test component has a purpose."""
        author = AuthorComponent()
        assert "document" in author.purpose.lower()

    def test_actions_registered(self):
        """Test all expected actions are registered."""
        author = AuthorComponent()
        expected_actions = [
            "create_document",
            "add_chapter",
            "add_section",
            "write_page",
            "edit_page",
            "delete_page",
            "search",
            "get_outline",
            "get_page",
            "get_context",
            "export_document",
        ]
        for action_name in expected_actions:
            assert author.get_action(action_name) is not None, f"Missing action: {action_name}"


class TestCreateDocument:
    """Test create_document action."""

    async def test_create_document(self, author_component, mock_doc_store, ctx):
        """Test creating a new document."""
        doc_id = uuid4()
        mock_doc_store.create_document.return_value = DocumentModel(
            id=doc_id,
            title="Test Book",
            author="Test Author",
        )

        result = await author_component.execute(
            "create_document",
            {"title": "Test Book", "author": "Test Author"},
            ctx,
        )

        assert result.title == "Test Book"
        assert result.author == "Test Author"
        assert result.created is True
        mock_doc_store.create_document.assert_called_once()

    async def test_create_document_without_author(self, author_component, mock_doc_store, ctx):
        """Test creating a document without author."""
        doc_id = uuid4()
        mock_doc_store.create_document.return_value = DocumentModel(
            id=doc_id,
            title="Untitled",
        )

        result = await author_component.execute(
            "create_document",
            {"title": "Untitled"},
            ctx,
        )

        assert result.title == "Untitled"
        assert result.author is None


class TestAddChapter:
    """Test add_chapter action."""

    async def test_add_chapter(self, author_component, mock_doc_store, ctx):
        """Test adding a chapter."""
        doc_id = uuid4()
        chapter_id = uuid4()

        mock_doc_store.create_chapter.return_value = ChapterModel(
            id=chapter_id,
            document_id=doc_id,
            title="Chapter 1",
            order_index=0,
        )

        result = await author_component.execute(
            "add_chapter",
            {"document_id": str(doc_id), "title": "Chapter 1"},
            ctx,
        )

        assert result.title == "Chapter 1"
        assert result.order_index == 0
        mock_doc_store.create_chapter.assert_called_once()

    async def test_add_chapter_with_summary(self, author_component, mock_doc_store, ctx):
        """Test adding a chapter with summary."""
        doc_id = uuid4()
        chapter_id = uuid4()

        mock_doc_store.create_chapter.return_value = ChapterModel(
            id=chapter_id,
            document_id=doc_id,
            title="Introduction",
            order_index=0,
            summary="An introduction to the topic.",
        )

        result = await author_component.execute(
            "add_chapter",
            {
                "document_id": str(doc_id),
                "title": "Introduction",
                "summary": "An introduction to the topic.",
            },
            ctx,
        )

        assert result.title == "Introduction"


class TestAddSection:
    """Test add_section action."""

    async def test_add_section(self, author_component, mock_doc_store, ctx):
        """Test adding a section."""
        chapter_id = uuid4()
        section_id = uuid4()

        mock_doc_store.create_section.return_value = SectionModel(
            id=section_id,
            chapter_id=chapter_id,
            title="Getting Started",
            order_index=0,
        )

        result = await author_component.execute(
            "add_section",
            {"chapter_id": str(chapter_id), "title": "Getting Started"},
            ctx,
        )

        assert result.title == "Getting Started"
        assert result.order_index == 0


class TestWritePage:
    """Test write_page action."""

    async def test_write_page(self, author_component, mock_doc_store, ctx):
        """Test writing a page."""
        section_id = uuid4()
        page_id = uuid4()
        chapter_id = uuid4()
        document_id = uuid4()

        mock_doc_store.create_page.return_value = PageModel(
            id=page_id,
            section_id=section_id,
            page_number=1,
            content="Hello world",
            word_count=2,
        )
        mock_doc_store.get_chapter_id_for_section.return_value = chapter_id
        mock_doc_store.get_document_id_for_chapter.return_value = document_id

        author_component._indexer.index_page = AsyncMock(return_value=[uuid4()])

        result = await author_component.execute(
            "write_page",
            {"section_id": str(section_id), "content": "Hello world"},
            ctx,
        )

        assert result.page_number == 1
        assert result.word_count == 2
        assert result.indexed is True

    async def test_write_page_indexing_failure(self, author_component, mock_doc_store, ctx):
        """Test page creation succeeds even if indexing fails."""
        section_id = uuid4()
        page_id = uuid4()

        mock_doc_store.create_page.return_value = PageModel(
            id=page_id,
            section_id=section_id,
            page_number=1,
            content="Test content",
            word_count=2,
        )
        mock_doc_store.get_chapter_id_for_section.return_value = None

        result = await author_component.execute(
            "write_page",
            {"section_id": str(section_id), "content": "Test content"},
            ctx,
        )

        assert result.indexed is False


class TestEditPage:
    """Test edit_page action."""

    async def test_edit_page(self, author_component, mock_doc_store, ctx):
        """Test editing a page."""
        page_id = uuid4()
        section_id = uuid4()
        document_id = uuid4()
        chapter_id = uuid4()

        mock_doc_store.update_page.return_value = PageModel(
            id=page_id,
            section_id=section_id,
            page_number=1,
            content="Updated content",
            word_count=2,
        )
        mock_doc_store.get_page_hierarchy.return_value = (
            document_id,
            chapter_id,
            section_id,
        )

        author_component._indexer.reindex_page = AsyncMock(return_value=[uuid4()])

        result = await author_component.execute(
            "edit_page",
            {"page_id": str(page_id), "content": "Updated content"},
            ctx,
        )

        assert result.word_count == 2
        assert result.indexed is True

    async def test_edit_page_not_found(self, author_component, mock_doc_store, ctx):
        """Test editing a non-existent page."""
        page_id = uuid4()
        mock_doc_store.update_page.return_value = None

        with pytest.raises(ValueError, match="Page not found"):
            await author_component.execute(
                "edit_page",
                {"page_id": str(page_id), "content": "New content"},
                ctx,
            )


class TestDeletePage:
    """Test delete_page action."""

    async def test_delete_page(self, author_component, mock_doc_store, ctx):
        """Test deleting a page."""
        page_id = uuid4()
        mock_doc_store.delete_page.return_value = True
        author_component._indexer.delete_page_chunks = AsyncMock(return_value=2)

        result = await author_component.execute(
            "delete_page",
            {"page_id": str(page_id)},
            ctx,
        )

        assert result.success is True
        assert result.deleted_id == str(page_id)


class TestSearch:
    """Test search action."""

    async def test_search(self, author_component, ctx):
        """Test semantic search."""
        page_id = uuid4()
        document_id = uuid4()
        chapter_id = uuid4()
        section_id = uuid4()

        author_component._retriever.search_to_hits.return_value = [
            SearchHit(
                chunk_id=uuid4(),
                text="This is a test result",
                similarity=0.95,
                location=PageLocation(
                    document_id=document_id,
                    document_title="Test Doc",
                    chapter_id=chapter_id,
                    chapter_title="Chapter 1",
                    chapter_index=0,
                    section_id=section_id,
                    section_title="Section 1",
                    section_index=0,
                    page_id=page_id,
                    page_number=1,
                ),
            )
        ]

        result = await author_component.execute(
            "search",
            {"query": "test query", "top_k": 5},
            ctx,
        )

        assert result.query == "test query"
        assert result.total == 1
        assert len(result.results) == 1
        assert result.results[0]["similarity"] == 0.95

    async def test_search_no_results(self, author_component, ctx):
        """Test search with no results."""
        author_component._retriever.search_to_hits.return_value = []

        result = await author_component.execute(
            "search",
            {"query": "nonexistent topic"},
            ctx,
        )

        assert result.total == 0
        assert len(result.results) == 0


class TestGetOutline:
    """Test get_outline action."""

    async def test_get_outline(self, author_component, mock_doc_store, ctx):
        """Test getting document outline."""
        document_id = uuid4()
        chapter_id = uuid4()
        section_id = uuid4()
        page_id = uuid4()

        mock_doc_store.get_outline.return_value = DocumentOutline(
            id=document_id,
            title="My Book",
            author="Test Author",
            chapter_count=1,
            section_count=1,
            page_count=1,
            word_count=100,
            chapters=[
                ChapterOutline(
                    id=chapter_id,
                    title="Chapter 1",
                    order_index=0,
                    sections=[
                        SectionOutline(
                            id=section_id,
                            title="Section 1",
                            order_index=0,
                            pages=[
                                PageOutline(
                                    id=page_id,
                                    page_number=1,
                                    word_count=100,
                                )
                            ],
                        )
                    ],
                )
            ],
        )

        result = await author_component.execute(
            "get_outline",
            {"document_id": str(document_id)},
            ctx,
        )

        assert result.title == "My Book"
        assert result.chapter_count == 1
        assert result.word_count == 100
        assert len(result.chapters) == 1

    async def test_get_outline_not_found(self, author_component, mock_doc_store, ctx):
        """Test getting outline for non-existent document."""
        document_id = uuid4()
        mock_doc_store.get_outline.return_value = None

        with pytest.raises(ValueError, match="Document not found"):
            await author_component.execute(
                "get_outline",
                {"document_id": str(document_id)},
                ctx,
            )


class TestGetPage:
    """Test get_page action."""

    async def test_get_page(self, author_component, mock_doc_store, ctx):
        """Test getting a page."""
        page_id = uuid4()
        section_id = uuid4()
        document_id = uuid4()
        chapter_id = uuid4()

        mock_doc_store.get_page.return_value = PageModel(
            id=page_id,
            section_id=section_id,
            page_number=1,
            content="Page content here",
            word_count=3,
        )

        mock_doc_store.get_page_location.return_value = PageLocation(
            document_id=document_id,
            document_title="My Book",
            chapter_id=chapter_id,
            chapter_title="Chapter 1",
            chapter_index=0,
            section_id=section_id,
            section_title="Section 1",
            section_index=0,
            page_id=page_id,
            page_number=1,
        )

        result = await author_component.execute(
            "get_page",
            {"page_id": str(page_id)},
            ctx,
        )

        assert result.content == "Page content here"
        assert result.page_number == 1
        assert result.location is not None
        assert result.location["chapter_title"] == "Chapter 1"


class TestGetContext:
    """Test get_context action."""

    async def test_get_context(self, author_component, mock_doc_store, ctx):
        """Test getting surrounding page context."""
        page_id = uuid4()

        mock_doc_store.get_surrounding_pages.return_value = (
            "[Page 1]\nPrevious page content\n\n---\n\n"
            "[Current Page 2]\nCurrent page content\n\n---\n\n"
            "[Page 3]\nNext page content"
        )

        result = await author_component.execute(
            "get_context",
            {"page_id": str(page_id), "window": 1},
            ctx,
        )

        assert "Current Page 2" in result.context
        assert result.window == 1


class TestToolExport:
    """Test exporting component actions as tool specs."""

    def test_to_function_tools(self):
        """Test OpenAI function tool export."""
        author = AuthorComponent()
        tools = author.to_function_tools()

        assert len(tools) == 14
        for tool in tools:
            assert tool["type"] == "function"
            assert "function" in tool
            assert "name" in tool["function"]
            assert "description" in tool["function"]
            assert "parameters" in tool["function"]

    def test_to_mcp_tools(self):
        """Test MCP tool export."""
        author = AuthorComponent()
        tools = author.to_mcp_tools()

        assert len(tools) == 14
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "inputSchema" in tool

    def test_to_anthropic_tools(self):
        """Test Anthropic tool export."""
        author = AuthorComponent()
        tools = author.to_anthropic_tools()

        assert len(tools) == 14
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool

    def test_system_prompt(self):
        """Test system prompt generation."""
        author = AuthorComponent()
        prompt = author.system_prompt()

        assert "author" in prompt.lower()
        assert "create_document" in prompt
        assert "search" in prompt
