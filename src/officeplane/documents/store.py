"""
Document storage using PostgreSQL.

Provides CRUD operations for documents, chapters, sections, and pages.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID

from officeplane.documents.models import (
    ChapterModel,
    ChapterOutline,
    DocumentModel,
    DocumentOutline,
    PageLocation,
    PageModel,
    PageOutline,
    SectionModel,
    SectionOutline,
)

log = logging.getLogger("officeplane.documents.store")

DEFAULT_DATABASE_URL = "postgresql://officeplane:officeplane@localhost:5432/officeplane"


class DocumentStore:
    """
    Document storage backed by PostgreSQL.

    Provides CRUD operations for the document hierarchy.
    """

    def __init__(self, database_url: Optional[str] = None) -> None:
        self.database_url = database_url or os.getenv(
            "DATABASE_URL", DEFAULT_DATABASE_URL
        )
        self._pool: Optional[Any] = None

    async def connect(self) -> None:
        """Connect to the database."""
        try:
            import asyncpg
        except ImportError:
            raise ImportError("asyncpg not installed. Install with: pip install asyncpg")

        self._pool = await asyncpg.create_pool(
            self.database_url,
            min_size=2,
            max_size=10,
        )
        log.info("Connected to document store")

    async def close(self) -> None:
        """Close the database connection."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def _get_pool(self) -> Any:
        if self._pool is None:
            await self.connect()
        return self._pool

    # ============================================================
    # Document Operations
    # ============================================================

    def _parse_metadata(self, metadata_value):
        """Parse metadata from database, handling both dict and string formats."""
        import json

        if isinstance(metadata_value, str):
            return json.loads(metadata_value)
        return metadata_value if metadata_value else {}

    async def create_document(
        self,
        title: str,
        author: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        summary: Optional[str] = None,
        topics: Optional[list] = None,
        key_entities: Optional[dict] = None,
    ) -> DocumentModel:
        """Create a new document."""
        import json

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO documents (title, author, metadata, summary, topics, key_entities, updated_at)
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
                RETURNING id, title, author, metadata, summary, topics, key_entities, created_at, updated_at
                """,
                title,
                author,
                json.dumps(metadata or {}),
                summary,
                topics or [],
                json.dumps(key_entities or {}),
            )

        return DocumentModel(
            id=row["id"],
            title=row["title"],
            author=row["author"],
            metadata=self._parse_metadata(row["metadata"]),
            summary=row["summary"],
            topics=list(row["topics"]) if row["topics"] else [],
            key_entities=self._parse_metadata(row["key_entities"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_document(
        self,
        document_id: UUID,
        load_children: bool = False,
    ) -> Optional[DocumentModel]:
        """Get a document by ID."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM documents WHERE id = $1",
                document_id,
            )

        if not row:
            return None

        doc = DocumentModel(
            id=row["id"],
            title=row["title"],
            author=row["author"],
            metadata=self._parse_metadata(row["metadata"]),
            summary=row["summary"],
            topics=list(row["topics"]) if row["topics"] else [],
            key_entities=self._parse_metadata(row["key_entities"]),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

        if load_children:
            doc.chapters = await self.list_chapters(document_id, load_children=True)

        return doc

    async def update_document(
        self,
        document_id: UUID,
        title: Optional[str] = None,
        author: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[DocumentModel]:
        """Update a document."""
        import json

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Build dynamic update
            updates: List[str] = []
            params: List[Any] = [document_id]
            idx = 2

            if title is not None:
                updates.append(f"title = ${idx}")
                params.append(title)
                idx += 1

            if author is not None:
                updates.append(f"author = ${idx}")
                params.append(author)
                idx += 1

            if metadata is not None:
                updates.append(f"metadata = ${idx}")
                params.append(json.dumps(metadata))
                idx += 1

            if not updates:
                return await self.get_document(document_id)

            query = f"""
                UPDATE documents
                SET {", ".join(updates)}
                WHERE id = $1
                RETURNING *
            """
            row = await conn.fetchrow(query, *params)

        if not row:
            return None

        return DocumentModel(
            id=row["id"],
            title=row["title"],
            author=row["author"],
            metadata=row["metadata"] if row["metadata"] else {},
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def delete_document(self, document_id: UUID) -> bool:
        """Delete a document and all its children (cascades)."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM documents WHERE id = $1",
                document_id,
            )
        return "DELETE 1" in result

    # ============================================================
    # Chapter Operations
    # ============================================================

    async def create_chapter(
        self,
        document_id: UUID,
        title: str,
        order_index: Optional[int] = None,
        summary: Optional[str] = None,
    ) -> ChapterModel:
        """Create a new chapter."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Auto-assign order if not provided
            if order_index is None:
                row = await conn.fetchrow(
                    "SELECT COALESCE(MAX(order_index), -1) + 1 as next_idx FROM chapters WHERE document_id = $1",
                    document_id,
                )
                order_index = row["next_idx"]

            row = await conn.fetchrow(
                """
                INSERT INTO chapters (document_id, title, order_index, summary, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
                RETURNING *
                """,
                document_id,
                title,
                order_index,
                summary,
            )

        return ChapterModel(
            id=row["id"],
            document_id=row["document_id"],
            title=row["title"],
            order_index=row["order_index"],
            summary=row["summary"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_chapter(
        self,
        chapter_id: UUID,
        load_children: bool = False,
    ) -> Optional[ChapterModel]:
        """Get a chapter by ID."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM chapters WHERE id = $1",
                chapter_id,
            )

        if not row:
            return None

        chapter = ChapterModel(
            id=row["id"],
            document_id=row["document_id"],
            title=row["title"],
            order_index=row["order_index"],
            summary=row["summary"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

        if load_children:
            chapter.sections = await self.list_sections(chapter_id, load_children=True)

        return chapter

    async def list_chapters(
        self,
        document_id: UUID,
        load_children: bool = False,
    ) -> List[ChapterModel]:
        """List chapters for a document."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM chapters WHERE document_id = $1 ORDER BY order_index",
                document_id,
            )

        chapters = []
        for row in rows:
            chapter = ChapterModel(
                id=row["id"],
                document_id=row["document_id"],
                title=row["title"],
                order_index=row["order_index"],
                summary=row["summary"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            if load_children:
                chapter.sections = await self.list_sections(
                    row["id"], load_children=True
                )
            chapters.append(chapter)

        return chapters

    async def update_chapter(
        self,
        chapter_id: UUID,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        order_index: Optional[int] = None,
    ) -> Optional[ChapterModel]:
        """Update a chapter."""
        pool = await self._get_pool()
        updates: List[str] = []
        params: List[Any] = [chapter_id]
        idx = 2

        if title is not None:
            updates.append(f"title = ${idx}")
            params.append(title)
            idx += 1

        if summary is not None:
            updates.append(f"summary = ${idx}")
            params.append(summary)
            idx += 1

        if order_index is not None:
            updates.append(f"order_index = ${idx}")
            params.append(order_index)
            idx += 1

        if not updates:
            return await self.get_chapter(chapter_id)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"UPDATE chapters SET {', '.join(updates)} WHERE id = $1 RETURNING *",
                *params,
            )

        if not row:
            return None

        return ChapterModel(
            id=row["id"],
            document_id=row["document_id"],
            title=row["title"],
            order_index=row["order_index"],
            summary=row["summary"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def delete_chapter(self, chapter_id: UUID) -> bool:
        """Delete a chapter."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM chapters WHERE id = $1",
                chapter_id,
            )
        return "DELETE 1" in result

    # ============================================================
    # Section Operations
    # ============================================================

    async def create_section(
        self,
        chapter_id: UUID,
        title: str,
        order_index: Optional[int] = None,
        summary: Optional[str] = None,
    ) -> SectionModel:
        """Create a new section."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if order_index is None:
                row = await conn.fetchrow(
                    "SELECT COALESCE(MAX(order_index), -1) + 1 as next_idx FROM sections WHERE chapter_id = $1",
                    chapter_id,
                )
                order_index = row["next_idx"]

            row = await conn.fetchrow(
                """
                INSERT INTO sections (chapter_id, title, order_index, summary, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
                RETURNING *
                """,
                chapter_id,
                title,
                order_index,
                summary,
            )

        return SectionModel(
            id=row["id"],
            chapter_id=row["chapter_id"],
            title=row["title"],
            order_index=row["order_index"],
            summary=row["summary"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_section(
        self,
        section_id: UUID,
        load_children: bool = False,
    ) -> Optional[SectionModel]:
        """Get a section by ID."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM sections WHERE id = $1",
                section_id,
            )

        if not row:
            return None

        section = SectionModel(
            id=row["id"],
            chapter_id=row["chapter_id"],
            title=row["title"],
            order_index=row["order_index"],
            summary=row["summary"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

        if load_children:
            section.pages = await self.list_pages(section_id)

        return section

    async def list_sections(
        self,
        chapter_id: UUID,
        load_children: bool = False,
    ) -> List[SectionModel]:
        """List sections for a chapter."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM sections WHERE chapter_id = $1 ORDER BY order_index",
                chapter_id,
            )

        sections = []
        for row in rows:
            section = SectionModel(
                id=row["id"],
                chapter_id=row["chapter_id"],
                title=row["title"],
                order_index=row["order_index"],
                summary=row["summary"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            if load_children:
                section.pages = await self.list_pages(row["id"])
            sections.append(section)

        return sections

    async def delete_section(self, section_id: UUID) -> bool:
        """Delete a section."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM sections WHERE id = $1",
                section_id,
            )
        return "DELETE 1" in result

    # ============================================================
    # Page Operations
    # ============================================================

    async def create_page(
        self,
        section_id: UUID,
        content: str = "",
        page_number: Optional[int] = None,
    ) -> PageModel:
        """Create a new page."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if page_number is None:
                row = await conn.fetchrow(
                    "SELECT COALESCE(MAX(page_number), 0) + 1 as next_num FROM pages WHERE section_id = $1",
                    section_id,
                )
                page_number = row["next_num"]

            word_count = len(content.split()) if content else 0

            row = await conn.fetchrow(
                """
                INSERT INTO pages (section_id, page_number, content, word_count, updated_at)
                VALUES ($1, $2, $3, $4, NOW())
                RETURNING *
                """,
                section_id,
                page_number,
                content,
                word_count,
            )

        return PageModel(
            id=row["id"],
            section_id=row["section_id"],
            page_number=row["page_number"],
            content=row["content"],
            word_count=row["word_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def get_page(self, page_id: UUID) -> Optional[PageModel]:
        """Get a page by ID."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM pages WHERE id = $1",
                page_id,
            )

        if not row:
            return None

        return PageModel(
            id=row["id"],
            section_id=row["section_id"],
            page_number=row["page_number"],
            content=row["content"],
            word_count=row["word_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def list_pages(self, section_id: UUID) -> List[PageModel]:
        """List pages for a section."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM pages WHERE section_id = $1 ORDER BY page_number",
                section_id,
            )

        return [
            PageModel(
                id=row["id"],
                section_id=row["section_id"],
                page_number=row["page_number"],
                content=row["content"],
                word_count=row["word_count"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    async def update_page(
        self,
        page_id: UUID,
        content: Optional[str] = None,
        page_number: Optional[int] = None,
    ) -> Optional[PageModel]:
        """Update a page."""
        pool = await self._get_pool()
        updates: List[str] = []
        params: List[Any] = [page_id]
        idx = 2

        if content is not None:
            updates.append(f"content = ${idx}")
            params.append(content)
            idx += 1
            updates.append(f"word_count = ${idx}")
            params.append(len(content.split()) if content else 0)
            idx += 1

        if page_number is not None:
            updates.append(f"page_number = ${idx}")
            params.append(page_number)
            idx += 1

        if not updates:
            return await self.get_page(page_id)

        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                f"UPDATE pages SET {', '.join(updates)} WHERE id = $1 RETURNING *",
                *params,
            )

        if not row:
            return None

        return PageModel(
            id=row["id"],
            section_id=row["section_id"],
            page_number=row["page_number"],
            content=row["content"],
            word_count=row["word_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    async def delete_page(self, page_id: UUID) -> bool:
        """Delete a page."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM pages WHERE id = $1",
                page_id,
            )
        return "DELETE 1" in result

    # ============================================================
    # Outline / TOC
    # ============================================================

    async def get_outline(self, document_id: UUID) -> Optional[DocumentOutline]:
        """Get document outline (table of contents)."""
        doc = await self.get_document(document_id, load_children=True)
        if not doc:
            return None

        chapters = []
        total_sections = 0
        total_pages = 0
        total_words = 0

        for chapter in doc.chapters:
            sections = []
            for section in chapter.sections:
                pages = [
                    PageOutline(
                        id=p.id,
                        page_number=p.page_number,
                        word_count=p.word_count,
                    )
                    for p in section.pages
                ]
                total_pages += len(pages)
                total_words += sum(p.word_count for p in section.pages)
                sections.append(
                    SectionOutline(
                        id=section.id,
                        title=section.title,
                        order_index=section.order_index,
                        pages=pages,
                    )
                )
            total_sections += len(sections)
            chapters.append(
                ChapterOutline(
                    id=chapter.id,
                    title=chapter.title,
                    order_index=chapter.order_index,
                    summary=chapter.summary,
                    sections=sections,
                )
            )

        return DocumentOutline(
            id=doc.id,
            title=doc.title,
            author=doc.author,
            chapter_count=len(chapters),
            section_count=total_sections,
            page_count=total_pages,
            word_count=total_words,
            chapters=chapters,
        )

    async def get_page_location(self, page_id: UUID) -> Optional[PageLocation]:
        """Get the location of a page within the document hierarchy."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT
                    d.id as document_id, d.title as document_title,
                    c.id as chapter_id, c.title as chapter_title, c.order_index as chapter_index,
                    s.id as section_id, s.title as section_title, s.order_index as section_index,
                    p.id as page_id, p.page_number
                FROM pages p
                JOIN sections s ON p.section_id = s.id
                JOIN chapters c ON s.chapter_id = c.id
                JOIN documents d ON c.document_id = d.id
                WHERE p.id = $1
                """,
                page_id,
            )

        if not row:
            return None

        return PageLocation(
            document_id=row["document_id"],
            document_title=row["document_title"],
            chapter_id=row["chapter_id"],
            chapter_title=row["chapter_title"],
            chapter_index=row["chapter_index"],
            section_id=row["section_id"],
            section_title=row["section_title"],
            section_index=row["section_index"],
            page_id=row["page_id"],
            page_number=row["page_number"],
        )

    async def get_surrounding_pages(
        self,
        page_id: UUID,
        window: int = 1,
    ) -> Optional[str]:
        """
        Get content from surrounding pages for context.

        Args:
            page_id: The center page
            window: Number of pages before/after to include

        Returns:
            Combined content from surrounding pages, or None if page not found
        """
        # First get the page's section and page number
        page = await self.get_page(page_id)
        if not page:
            return None

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            # Get pages within window around this page's number
            rows = await conn.fetch(
                """
                SELECT content, page_number
                FROM pages
                WHERE section_id = $1
                  AND page_number BETWEEN $2 AND $3
                ORDER BY page_number
                """,
                page.section_id,
                page.page_number - window,
                page.page_number + window,
            )

        if not rows:
            return None

        # Combine content with page markers
        parts = []
        for row in rows:
            if row["page_number"] == page.page_number:
                parts.append(f"[Current Page {row['page_number']}]\n{row['content']}")
            else:
                parts.append(f"[Page {row['page_number']}]\n{row['content']}")

        return "\n\n---\n\n".join(parts)

    async def get_document_id_for_chapter(self, chapter_id: UUID) -> Optional[UUID]:
        """Get the document ID for a chapter."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT document_id FROM chapters WHERE id = $1",
                chapter_id,
            )
        return row["document_id"] if row else None

    async def get_chapter_id_for_section(self, section_id: UUID) -> Optional[UUID]:
        """Get the chapter ID for a section."""
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT chapter_id FROM sections WHERE id = $1",
                section_id,
            )
        return row["chapter_id"] if row else None

    async def get_page_hierarchy(
        self, page_id: UUID
    ) -> Optional[tuple[UUID, UUID, UUID]]:
        """
        Get the full hierarchy IDs for a page.

        Returns:
            Tuple of (document_id, chapter_id, section_id), or None if not found
        """
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT d.id as document_id, c.id as chapter_id, s.id as section_id
                FROM pages p
                JOIN sections s ON p.section_id = s.id
                JOIN chapters c ON s.chapter_id = c.id
                JOIN documents d ON c.document_id = d.id
                WHERE p.id = $1
                """,
                page_id,
            )
        if not row:
            return None
        return (row["document_id"], row["chapter_id"], row["section_id"])
