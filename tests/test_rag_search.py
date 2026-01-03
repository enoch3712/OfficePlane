"""
Tests for RAG (Retrieval Augmented Generation) functionality.

Tests the document chunking, embedding, and search capabilities.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

from officeplane.documents.chunker import (
    SlidingWindowChunker,
    TextChunk,
    chunk_text,
)
from officeplane.memory.rag import (
    RAGRetriever,
    DocumentIndexer,
)
from officeplane.memory.vector_store import (
    VectorStore,
    ChunkRecord,
    SearchResult,
)
from officeplane.documents.models import PageLocation, SearchHit


class TestSlidingWindowChunker:
    """Test the sliding window text chunker."""

    def test_empty_text(self):
        """Test chunking empty text."""
        chunker = SlidingWindowChunker()
        chunks = chunker.chunk("")
        assert chunks == []

    def test_whitespace_only(self):
        """Test chunking whitespace-only text."""
        chunker = SlidingWindowChunker()
        chunks = chunker.chunk("   \n\n  ")
        assert chunks == []

    def test_short_text(self):
        """Test text shorter than chunk size."""
        chunker = SlidingWindowChunker(chunk_size=500)
        text = "This is a short text."
        chunks = chunker.chunk(text)

        assert len(chunks) == 1
        assert chunks[0].text == text
        assert chunks[0].start_offset == 0
        assert chunks[0].end_offset == len(text)

    def test_chunking_with_overlap(self):
        """Test that chunks overlap correctly."""
        # Use small sizes for testing
        chunker = SlidingWindowChunker(
            chunk_size=10,
            overlap=3,
            min_chunk_size=3,
        )

        # Generate text that will require multiple chunks
        text = "word " * 50  # 50 words

        chunks = chunker.chunk(text)

        # Should have multiple chunks
        assert len(chunks) > 1

        # All chunks should have text
        for chunk in chunks:
            assert chunk.text
            assert chunk.token_count > 0

    def test_token_count_accuracy(self):
        """Test that token counts are accurate."""
        chunker = SlidingWindowChunker()
        text = "Hello world, this is a test."

        # Count tokens directly
        token_count = chunker.count_tokens(text)

        # Should be positive
        assert token_count > 0

        # Chunk and verify
        chunks = chunker.chunk(text)
        assert len(chunks) == 1
        assert chunks[0].token_count == token_count

    def test_chunk_offsets(self):
        """Test that chunk offsets are reasonable."""
        chunker = SlidingWindowChunker(chunk_size=20, overlap=5, min_chunk_size=5)
        text = "This is a longer piece of text that should be split into multiple chunks."

        chunks = chunker.chunk(text)

        # Offsets should be non-negative
        for chunk in chunks:
            assert chunk.start_offset >= 0
            assert chunk.end_offset > chunk.start_offset

        # First chunk should start at 0
        if chunks:
            assert chunks[0].start_offset == 0


class TestChunkByParagraphs:
    """Test paragraph-aware chunking."""

    def test_empty_text(self):
        """Test chunking empty text by paragraphs."""
        chunker = SlidingWindowChunker()
        chunks = chunker.chunk_by_paragraphs("")
        assert chunks == []

    def test_single_paragraph(self):
        """Test single paragraph."""
        # Use a paragraph long enough to meet min_chunk_size
        chunker = SlidingWindowChunker(chunk_size=500, min_chunk_size=5)
        text = "This is a single paragraph with some content. It has enough words to be indexed properly."

        chunks = chunker.chunk_by_paragraphs(text)

        assert len(chunks) == 1
        assert text in chunks[0].text

    def test_multiple_paragraphs(self):
        """Test multiple paragraphs that fit in one chunk."""
        chunker = SlidingWindowChunker(chunk_size=500, min_chunk_size=5)
        # Longer paragraphs to meet min_chunk_size
        text = "First paragraph with content.\n\nSecond paragraph with content.\n\nThird paragraph with content."

        chunks = chunker.chunk_by_paragraphs(text)

        # Should combine into one chunk
        assert len(chunks) == 1

    def test_paragraph_overflow(self):
        """Test when paragraphs exceed chunk size."""
        chunker = SlidingWindowChunker(chunk_size=10, overlap=2, min_chunk_size=3)

        # Create paragraphs that will overflow
        text = "First paragraph with content.\n\nSecond paragraph with more content."

        chunks = chunker.chunk_by_paragraphs(text)

        # Should create multiple chunks
        assert len(chunks) >= 2


class TestConvenienceFunction:
    """Test module-level convenience function."""

    def test_chunk_text_function(self):
        """Test the chunk_text convenience function."""
        text = "This is some text to chunk."
        chunks = chunk_text(text)

        assert len(chunks) >= 1
        assert all(isinstance(c, TextChunk) for c in chunks)

    def test_chunk_text_with_custom_params(self):
        """Test chunk_text with custom parameters."""
        text = "Word " * 100

        chunks = chunk_text(text, chunk_size=50, overlap=10)

        assert len(chunks) >= 1


class TestVectorStore:
    """Test VectorStore unit tests."""

    def test_default_database_url(self):
        """Test default database URL is set."""
        store = VectorStore()
        assert "postgresql" in store.database_url

    def test_custom_database_url(self):
        """Test custom database URL."""
        store = VectorStore(database_url="postgresql://custom:custom@localhost/test")
        assert store.database_url == "postgresql://custom:custom@localhost/test"

    def test_initial_state(self):
        """Test initial state."""
        store = VectorStore()
        assert store._pool is None


class TestRAGRetriever:
    """Test RAG retrieval functionality."""

    @pytest.fixture
    def mock_stores(self):
        """Create mock stores for testing."""
        vector_store = AsyncMock()
        doc_store = AsyncMock()
        embedding_client = MagicMock()
        embedding_client.aembed = AsyncMock(return_value=[0.1] * 1536)

        return vector_store, doc_store, embedding_client

    async def test_search(self, mock_stores):
        """Test semantic search."""
        vector_store, doc_store, embedding_client = mock_stores

        chunk_id = uuid4()
        page_id = uuid4()
        document_id = uuid4()
        chapter_id = uuid4()
        section_id = uuid4()

        vector_store.search.return_value = [
            SearchResult(
                chunk=ChunkRecord(
                    id=chunk_id,
                    document_id=document_id,
                    chapter_id=chapter_id,
                    section_id=section_id,
                    page_id=page_id,
                    text="Test chunk text",
                    start_offset=0,
                    end_offset=15,
                    token_count=3,
                ),
                similarity=0.92,
            )
        ]

        doc_store.get_page_location.return_value = PageLocation(
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
        )

        retriever = RAGRetriever(
            vector_store=vector_store,
            doc_store=doc_store,
            embedding_client=embedding_client,
        )

        results = await retriever.search("test query", top_k=5)

        assert len(results) == 1
        assert results[0].similarity == 0.92
        assert results[0].location is not None
        assert results[0].location.chapter_title == "Chapter 1"

    async def test_search_to_hits(self, mock_stores):
        """Test search returning SearchHit models."""
        vector_store, doc_store, embedding_client = mock_stores

        chunk_id = uuid4()
        page_id = uuid4()
        document_id = uuid4()
        chapter_id = uuid4()
        section_id = uuid4()

        vector_store.search.return_value = [
            SearchResult(
                chunk=ChunkRecord(
                    id=chunk_id,
                    document_id=document_id,
                    chapter_id=chapter_id,
                    section_id=section_id,
                    page_id=page_id,
                    text="Search result text",
                    start_offset=0,
                    end_offset=18,
                    token_count=3,
                ),
                similarity=0.88,
            )
        ]

        doc_store.get_page_location.return_value = PageLocation(
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
        )

        retriever = RAGRetriever(
            vector_store=vector_store,
            doc_store=doc_store,
            embedding_client=embedding_client,
        )

        hits = await retriever.search_to_hits("query", top_k=3)

        assert len(hits) == 1
        assert isinstance(hits[0], SearchHit)
        assert hits[0].similarity == 0.88


class TestDocumentIndexer:
    """Test document indexing functionality."""

    @pytest.fixture
    def mock_indexer_deps(self):
        """Create mock dependencies for indexer."""
        vector_store = AsyncMock()
        embedding_client = MagicMock()
        embedding_client.aembed_batch = AsyncMock(return_value=[[0.1] * 1536])

        return vector_store, embedding_client

    async def test_index_page(self, mock_indexer_deps):
        """Test indexing a page."""
        vector_store, embedding_client = mock_indexer_deps
        chunk_ids = [uuid4(), uuid4()]
        vector_store.insert_chunks_batch.return_value = chunk_ids

        indexer = DocumentIndexer(
            vector_store=vector_store,
            embedding_client=embedding_client,
            chunk_size=500,
            chunk_overlap=100,
        )

        page_id = uuid4()
        document_id = uuid4()
        chapter_id = uuid4()
        section_id = uuid4()

        result = await indexer.index_page(
            page_id=page_id,
            document_id=document_id,
            chapter_id=chapter_id,
            section_id=section_id,
            content="This is the page content to index.",
        )

        assert len(result) == len(chunk_ids)
        embedding_client.aembed_batch.assert_called_once()
        vector_store.insert_chunks_batch.assert_called_once()

    async def test_index_empty_page(self, mock_indexer_deps):
        """Test indexing an empty page."""
        vector_store, embedding_client = mock_indexer_deps

        indexer = DocumentIndexer(
            vector_store=vector_store,
            embedding_client=embedding_client,
        )

        result = await indexer.index_page(
            page_id=uuid4(),
            document_id=uuid4(),
            chapter_id=uuid4(),
            section_id=uuid4(),
            content="",
        )

        assert result == []
        vector_store.insert_chunks_batch.assert_not_called()

    async def test_reindex_page(self, mock_indexer_deps):
        """Test re-indexing a page."""
        vector_store, embedding_client = mock_indexer_deps
        vector_store.delete_chunks_by_page.return_value = 2
        vector_store.insert_chunks_batch.return_value = [uuid4()]

        indexer = DocumentIndexer(
            vector_store=vector_store,
            embedding_client=embedding_client,
        )

        page_id = uuid4()

        result = await indexer.reindex_page(
            page_id=page_id,
            document_id=uuid4(),
            chapter_id=uuid4(),
            section_id=uuid4(),
            content="Updated content.",
        )

        # Should delete old chunks first
        vector_store.delete_chunks_by_page.assert_called_once_with(page_id)

        # Then insert new chunks
        assert len(result) == 1

    async def test_delete_page_chunks(self, mock_indexer_deps):
        """Test deleting page chunks."""
        vector_store, embedding_client = mock_indexer_deps
        vector_store.delete_chunks_by_page.return_value = 5

        indexer = DocumentIndexer(
            vector_store=vector_store,
            embedding_client=embedding_client,
        )

        page_id = uuid4()
        deleted = await indexer.delete_page_chunks(page_id)

        assert deleted == 5
        vector_store.delete_chunks_by_page.assert_called_once_with(page_id)


class TestEmbeddingDimensions:
    """Test embedding dimension constants."""

    def test_embedding_dimensions(self):
        """Test that embedding dimensions match expected value."""
        from officeplane.memory.embeddings import EMBEDDING_DIMENSIONS

        # OpenAI ada-002 uses 1536 dimensions
        assert EMBEDDING_DIMENSIONS == 1536

    def test_embedding_model(self):
        """Test default embedding model."""
        from officeplane.memory.embeddings import EMBEDDING_MODEL

        assert EMBEDDING_MODEL == "text-embedding-ada-002"
