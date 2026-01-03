"""
Vector storage using PostgreSQL with pgvector.

Provides CRUD operations and similarity search for document chunks.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID
from typing import cast

log = logging.getLogger("officeplane.memory.vector_store")

# Default connection string
DEFAULT_DATABASE_URL = "postgresql://officeplane:officeplane@localhost:5432/officeplane"


@dataclass
class ChunkRecord:
    """A chunk record from the database."""

    id: UUID
    document_id: UUID
    chapter_id: UUID
    section_id: UUID
    page_id: UUID
    text: str
    start_offset: int
    end_offset: int
    token_count: int
    embedding: Optional[List[float]] = None


@dataclass
class SearchResult:
    """A search result with similarity score."""

    chunk: ChunkRecord
    similarity: float


class VectorStore:
    """
    Vector store backed by PostgreSQL + pgvector.

    Provides:
    - Store chunks with embeddings
    - Similarity search
    - CRUD operations for chunks

    Usage:
        store = VectorStore()
        await store.connect()

        # Store a chunk
        chunk_id = await store.insert_chunk(
            document_id=doc_id,
            chapter_id=ch_id,
            section_id=sec_id,
            page_id=page_id,
            text="Hello world",
            start_offset=0,
            end_offset=11,
            embedding=[0.1, 0.2, ...]
        )

        # Search
        results = await store.search(query_embedding, top_k=5)

        await store.close()
    """

    def __init__(self, database_url: Optional[str] = None) -> None:
        """
        Initialize the vector store.

        Args:
            database_url: PostgreSQL connection string
        """
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", DEFAULT_DATABASE_URL
        )
        self._pool: Optional[Any] = None

    async def connect(self) -> None:
        """Connect to the database."""
        try:
            import asyncpg
        except ImportError:
            raise ImportError(
                "asyncpg package not installed. "
                "Install with: pip install asyncpg"
            )

        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=10,
        )
        log.info("Connected to vector store")

    async def close(self) -> None:
        """Close the database connection."""
        if self._pool:
            await self._pool.close()
            self._pool = None
            log.info("Disconnected from vector store")

    async def _get_pool(self) -> Any:
        """Get the connection pool, connecting if needed."""
        if self._pool is None:
            await self.connect()
        return self._pool

    async def insert_chunk(
        self,
        document_id: UUID,
        chapter_id: UUID,
        section_id: UUID,
        page_id: UUID,
        text: str,
        start_offset: int,
        end_offset: int,
        embedding: List[float],
        token_count: int = 0,
    ) -> UUID:
        """
        Insert a chunk with its embedding.

        Returns:
            The chunk ID
        """
        pool = await self._get_pool()

        # Convert embedding list to pgvector format
        embedding_str = "[" + ",".join(str(x) for x in embedding) + "]"

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO chunks (
                    document_id, chapter_id, section_id, page_id,
                    text, start_offset, end_offset, token_count, embedding
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::vector)
                RETURNING id
                """,
                document_id,
                chapter_id,
                section_id,
                page_id,
                text,
                start_offset,
                end_offset,
                token_count,
                embedding_str,
            )
            return cast(UUID, row["id"])

    async def insert_chunks_batch(
        self,
        chunks: List[Dict[str, Any]],
    ) -> List[UUID]:
        """
        Insert multiple chunks in a batch.

        Args:
            chunks: List of dicts with keys:
                document_id, chapter_id, section_id, page_id,
                text, start_offset, end_offset, embedding, token_count

        Returns:
            List of chunk IDs
        """
        if not chunks:
            return []

        pool = await self._get_pool()
        ids = []

        async with pool.acquire() as conn:
            async with conn.transaction():
                for chunk in chunks:
                    embedding_str = (
                        "[" + ",".join(str(x) for x in chunk["embedding"]) + "]"
                    )
                    row = await conn.fetchrow(
                        """
                        INSERT INTO chunks (
                            document_id, chapter_id, section_id, page_id,
                            text, start_offset, end_offset, token_count, embedding
                        )
                        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9::vector)
                        RETURNING id
                        """,
                        chunk["document_id"],
                        chunk["chapter_id"],
                        chunk["section_id"],
                        chunk["page_id"],
                        chunk["text"],
                        chunk["start_offset"],
                        chunk["end_offset"],
                        chunk.get("token_count", 0),
                        embedding_str,
                    )
                    ids.append(row["id"])

        return ids

    async def search(
        self,
        query_embedding: List[float],
        top_k: int = 5,
        document_id: Optional[UUID] = None,
    ) -> List[SearchResult]:
        """
        Search for similar chunks.

        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            document_id: Optional filter by document

        Returns:
            List of SearchResult with chunks and similarity scores
        """
        pool = await self._get_pool()
        embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

        async with pool.acquire() as conn:
            if document_id:
                rows = await conn.fetch(
                    """
                    SELECT
                        id, document_id, chapter_id, section_id, page_id,
                        text, start_offset, end_offset, token_count,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM chunks
                    WHERE document_id = $3
                    ORDER BY embedding <=> $1::vector
                    LIMIT $2
                    """,
                    embedding_str,
                    top_k,
                    document_id,
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT
                        id, document_id, chapter_id, section_id, page_id,
                        text, start_offset, end_offset, token_count,
                        1 - (embedding <=> $1::vector) as similarity
                    FROM chunks
                    ORDER BY embedding <=> $1::vector
                    LIMIT $2
                    """,
                    embedding_str,
                    top_k,
                )

        results = []
        for row in rows:
            chunk = ChunkRecord(
                id=row["id"],
                document_id=row["document_id"],
                chapter_id=row["chapter_id"],
                section_id=row["section_id"],
                page_id=row["page_id"],
                text=row["text"],
                start_offset=row["start_offset"],
                end_offset=row["end_offset"],
                token_count=row["token_count"],
            )
            results.append(SearchResult(chunk=chunk, similarity=row["similarity"]))

        return results

    async def delete_chunks_by_page(self, page_id: UUID) -> int:
        """
        Delete all chunks for a page.

        Returns:
            Number of deleted chunks
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM chunks WHERE page_id = $1",
                page_id,
            )
            # Result is like "DELETE 5"
            return int(result.split()[-1])

    async def delete_chunks_by_document(self, document_id: UUID) -> int:
        """
        Delete all chunks for a document.

        Returns:
            Number of deleted chunks
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM chunks WHERE document_id = $1",
                document_id,
            )
            return int(result.split()[-1])

    async def get_chunk(self, chunk_id: UUID) -> Optional[ChunkRecord]:
        """Get a chunk by ID."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, document_id, chapter_id, section_id, page_id,
                       text, start_offset, end_offset, token_count
                FROM chunks WHERE id = $1
                """,
                chunk_id,
            )

        if not row:
            return None

        return ChunkRecord(
            id=row["id"],
            document_id=row["document_id"],
            chapter_id=row["chapter_id"],
            section_id=row["section_id"],
            page_id=row["page_id"],
            text=row["text"],
            start_offset=row["start_offset"],
            end_offset=row["end_offset"],
            token_count=row["token_count"],
        )

    async def count_chunks(self, document_id: Optional[UUID] = None) -> int:
        """Count chunks, optionally filtered by document."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if document_id:
                row = await conn.fetchrow(
                    "SELECT COUNT(*) FROM chunks WHERE document_id = $1",
                    document_id,
                )
            else:
                row = await conn.fetchrow("SELECT COUNT(*) FROM chunks")
            return cast(int, row[0])
