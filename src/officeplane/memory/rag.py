"""
RAG (Retrieval Augmented Generation) utilities.

Combines embedding generation, vector search, and document context
for semantic search over document chunks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional
from uuid import UUID

from officeplane.documents.models import PageLocation, SearchHit
from officeplane.documents.store import DocumentStore
from officeplane.memory.embeddings import EmbeddingClient
from officeplane.memory.vector_store import VectorStore

log = logging.getLogger("officeplane.memory.rag")


@dataclass
class RAGResult:
    """A RAG search result with full context."""

    chunk_id: UUID
    text: str
    similarity: float
    location: Optional[PageLocation]
    surrounding_context: Optional[str] = None


class RAGRetriever:
    """
    Retrieval system combining semantic search with document context.

    Provides:
    - Semantic search over document chunks
    - Location context for each result
    - Optional surrounding page content

    Usage:
        retriever = RAGRetriever(
            vector_store=VectorStore(),
            doc_store=DocumentStore(),
            embedding_client=EmbeddingClient()
        )
        await retriever.connect()

        results = await retriever.search("What is the main topic?", top_k=5)
        for r in results:
            print(f"{r.similarity:.2f}: {r.text[:100]}...")
            print(f"  Location: {r.location.chapter_title} > {r.location.section_title}")

        await retriever.close()
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        doc_store: Optional[DocumentStore] = None,
        embedding_client: Optional[EmbeddingClient] = None,
    ) -> None:
        """
        Initialize the RAG retriever.

        Args:
            vector_store: Vector store for similarity search
            doc_store: Document store for context retrieval
            embedding_client: Client for generating query embeddings
        """
        self.vector_store = vector_store or VectorStore()
        self.doc_store = doc_store or DocumentStore()
        self.embedding_client = embedding_client or EmbeddingClient()

    async def connect(self) -> None:
        """Connect to underlying stores."""
        await self.vector_store.connect()
        await self.doc_store.connect()
        log.info("RAG retriever connected")

    async def close(self) -> None:
        """Close connections."""
        await self.vector_store.close()
        await self.doc_store.close()
        log.info("RAG retriever disconnected")

    async def search(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[UUID] = None,
        include_context: bool = True,
    ) -> List[RAGResult]:
        """
        Search for relevant chunks.

        Args:
            query: Natural language query
            top_k: Number of results to return
            document_id: Optional filter to specific document
            include_context: Whether to fetch location context

        Returns:
            List of RAGResult with text, similarity, and optional location
        """
        # Generate query embedding
        query_embedding = await self.embedding_client.aembed(query)

        # Search vector store
        search_results = await self.vector_store.search(
            query_embedding=query_embedding,
            top_k=top_k,
            document_id=document_id,
        )

        # Build results with context
        results = []
        for sr in search_results:
            location = None
            if include_context:
                location = await self.doc_store.get_page_location(sr.chunk.page_id)

            results.append(
                RAGResult(
                    chunk_id=sr.chunk.id,
                    text=sr.chunk.text,
                    similarity=sr.similarity,
                    location=location,
                )
            )

        return results

    async def search_with_context(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[UUID] = None,
        context_window: int = 1,
    ) -> List[RAGResult]:
        """
        Search with surrounding page content.

        Args:
            query: Natural language query
            top_k: Number of results
            document_id: Optional document filter
            context_window: Number of pages before/after to include

        Returns:
            Results with surrounding_context filled in
        """
        results = await self.search(
            query=query,
            top_k=top_k,
            document_id=document_id,
            include_context=True,
        )

        # Fetch surrounding context for each result
        for result in results:
            if result.location:
                context = await self.doc_store.get_surrounding_pages(
                    page_id=result.location.page_id,
                    window=context_window,
                )
                if context:
                    result.surrounding_context = context

        return results

    async def search_to_hits(
        self,
        query: str,
        top_k: int = 5,
        document_id: Optional[UUID] = None,
    ) -> List[SearchHit]:
        """
        Search and return as SearchHit models.

        This is the format expected by the AuthorComponent.

        Args:
            query: Natural language query
            top_k: Number of results
            document_id: Optional document filter

        Returns:
            List of SearchHit Pydantic models
        """
        results = await self.search(
            query=query,
            top_k=top_k,
            document_id=document_id,
            include_context=True,
        )

        hits = []
        for r in results:
            if r.location:
                hits.append(
                    SearchHit(
                        chunk_id=r.chunk_id,
                        text=r.text,
                        similarity=r.similarity,
                        location=r.location,
                    )
                )

        return hits


class DocumentIndexer:
    """
    Index document pages for RAG search.

    Handles chunking page content and storing embeddings.

    Usage:
        indexer = DocumentIndexer(
            vector_store=VectorStore(),
            embedding_client=EmbeddingClient()
        )
        await indexer.connect()

        # Index a page
        chunk_ids = await indexer.index_page(
            page_id=page_id,
            document_id=doc_id,
            chapter_id=ch_id,
            section_id=sec_id,
            content="Page content here..."
        )

        # Re-index after edit
        await indexer.reindex_page(page_id, new_content, ...)

        await indexer.close()
    """

    def __init__(
        self,
        vector_store: Optional[VectorStore] = None,
        embedding_client: Optional[EmbeddingClient] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
    ) -> None:
        """
        Initialize the indexer.

        Args:
            vector_store: Vector store for chunk storage
            embedding_client: Client for generating embeddings
            chunk_size: Target tokens per chunk
            chunk_overlap: Overlap tokens between chunks
        """
        self.vector_store = vector_store or VectorStore()
        self.embedding_client = embedding_client or EmbeddingClient()
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self._chunker: Optional[object] = None

    def _get_chunker(self) -> object:
        """Lazy-load the chunker."""
        if self._chunker is None:
            from officeplane.documents.chunker import SlidingWindowChunker

            self._chunker = SlidingWindowChunker(
                chunk_size=self.chunk_size,
                overlap=self.chunk_overlap,
            )
        return self._chunker

    async def connect(self) -> None:
        """Connect to vector store."""
        await self.vector_store.connect()
        log.info("Document indexer connected")

    async def close(self) -> None:
        """Close connections."""
        await self.vector_store.close()
        log.info("Document indexer disconnected")

    async def index_page(
        self,
        page_id: UUID,
        document_id: UUID,
        chapter_id: UUID,
        section_id: UUID,
        content: str,
    ) -> List[UUID]:
        """
        Index a page's content.

        Chunks the content, generates embeddings, and stores in vector DB.

        Args:
            page_id: Page identifier
            document_id: Parent document
            chapter_id: Parent chapter
            section_id: Parent section
            content: Page text content

        Returns:
            List of created chunk IDs
        """
        if not content or not content.strip():
            return []

        # Chunk the content
        chunker = self._get_chunker()
        text_chunks = chunker.chunk(content)  # type: ignore

        if not text_chunks:
            return []

        # Generate embeddings for all chunks
        texts = [tc.text for tc in text_chunks]
        embeddings = await self.embedding_client.aembed_batch(texts)

        # Prepare batch insert
        chunks_data = []
        for tc, embedding in zip(text_chunks, embeddings):
            chunks_data.append(
                {
                    "document_id": document_id,
                    "chapter_id": chapter_id,
                    "section_id": section_id,
                    "page_id": page_id,
                    "text": tc.text,
                    "start_offset": tc.start_offset,
                    "end_offset": tc.end_offset,
                    "token_count": tc.token_count,
                    "embedding": embedding,
                }
            )

        # Insert all chunks
        chunk_ids = await self.vector_store.insert_chunks_batch(chunks_data)
        log.info(f"Indexed {len(chunk_ids)} chunks for page {page_id}")

        return chunk_ids

    async def reindex_page(
        self,
        page_id: UUID,
        document_id: UUID,
        chapter_id: UUID,
        section_id: UUID,
        content: str,
    ) -> List[UUID]:
        """
        Re-index a page after content update.

        Deletes existing chunks and creates new ones.

        Args:
            page_id: Page to re-index
            document_id: Parent document
            chapter_id: Parent chapter
            section_id: Parent section
            content: New page content

        Returns:
            List of new chunk IDs
        """
        # Delete existing chunks
        deleted = await self.vector_store.delete_chunks_by_page(page_id)
        log.info(f"Deleted {deleted} existing chunks for page {page_id}")

        # Index new content
        return await self.index_page(
            page_id=page_id,
            document_id=document_id,
            chapter_id=chapter_id,
            section_id=section_id,
            content=content,
        )

    async def delete_page_chunks(self, page_id: UUID) -> int:
        """
        Delete all chunks for a page.

        Args:
            page_id: Page to delete chunks for

        Returns:
            Number of deleted chunks
        """
        return await self.vector_store.delete_chunks_by_page(page_id)

    async def delete_document_chunks(self, document_id: UUID) -> int:
        """
        Delete all chunks for a document.

        Args:
            document_id: Document to delete chunks for

        Returns:
            Number of deleted chunks
        """
        return await self.vector_store.delete_chunks_by_document(document_id)


# Module-level convenience instances
_retriever: Optional[RAGRetriever] = None
_indexer: Optional[DocumentIndexer] = None


async def get_retriever() -> RAGRetriever:
    """Get or create the default RAG retriever."""
    global _retriever
    if _retriever is None:
        _retriever = RAGRetriever()
        await _retriever.connect()
    return _retriever


async def get_indexer() -> DocumentIndexer:
    """Get or create the default document indexer."""
    global _indexer
    if _indexer is None:
        _indexer = DocumentIndexer()
        await _indexer.connect()
    return _indexer


async def search(
    query: str,
    top_k: int = 5,
    document_id: Optional[UUID] = None,
) -> List[SearchHit]:
    """
    Convenience function for semantic search.

    Args:
        query: Natural language query
        top_k: Number of results
        document_id: Optional document filter

    Returns:
        List of SearchHit results
    """
    retriever = await get_retriever()
    return await retriever.search_to_hits(query, top_k, document_id)
