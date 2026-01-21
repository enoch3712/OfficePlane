"""
Document domain models.

Pydantic models for the document hierarchy:
Document -> Chapter -> Section -> Page -> Chunk
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


class ChunkModel(BaseModel):
    """A text chunk for RAG embedding."""

    id: UUID = Field(default_factory=uuid4)
    page_id: UUID
    document_id: UUID
    chapter_id: UUID
    section_id: UUID
    text: str
    start_offset: int
    end_offset: int
    token_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(from_attributes=True)


class PageModel(BaseModel):
    """A page within a section."""

    id: UUID = Field(default_factory=uuid4)
    section_id: UUID
    page_number: int
    content: str = ""
    word_count: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Loaded chunks (not persisted directly)
    chunks: List[ChunkModel] = Field(default_factory=list, exclude=True)

    model_config = ConfigDict(from_attributes=True)

    def update_word_count(self) -> None:
        """Update word count based on content."""
        self.word_count = len(self.content.split()) if self.content else 0


class SectionModel(BaseModel):
    """A section within a chapter."""

    id: UUID = Field(default_factory=uuid4)
    chapter_id: UUID
    title: str
    order_index: int
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Child pages (loaded separately)
    pages: List[PageModel] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @property
    def page_count(self) -> int:
        return len(self.pages)


class ChapterModel(BaseModel):
    """A chapter within a document."""

    id: UUID = Field(default_factory=uuid4)
    document_id: UUID
    title: str
    order_index: int
    summary: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Child sections (loaded separately)
    sections: List[SectionModel] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @property
    def section_count(self) -> int:
        return len(self.sections)

    @property
    def page_count(self) -> int:
        return sum(s.page_count for s in self.sections)


class DocumentModel(BaseModel):
    """A document (book-level container)."""

    id: UUID = Field(default_factory=uuid4)
    title: str
    author: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Child chapters (loaded separately)
    chapters: List[ChapterModel] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)

    @property
    def chapter_count(self) -> int:
        return len(self.chapters)

    @property
    def section_count(self) -> int:
        return sum(c.section_count for c in self.chapters)

    @property
    def page_count(self) -> int:
        return sum(c.page_count for c in self.chapters)

    @property
    def word_count(self) -> int:
        """Total word count across all pages."""
        total = 0
        for chapter in self.chapters:
            for section in chapter.sections:
                for page in section.pages:
                    total += page.word_count
        return total


# ============================================================
# Outline Models (for TOC)
# ============================================================


class PageOutline(BaseModel):
    """Page in outline view."""

    id: UUID
    page_number: int
    word_count: int


class SectionOutline(BaseModel):
    """Section in outline view."""

    id: UUID
    title: str
    order_index: int
    pages: List[PageOutline] = Field(default_factory=list)


class ChapterOutline(BaseModel):
    """Chapter in outline view."""

    id: UUID
    title: str
    order_index: int
    summary: Optional[str] = None
    sections: List[SectionOutline] = Field(default_factory=list)


class DocumentOutline(BaseModel):
    """Document outline (table of contents)."""

    id: UUID
    title: str
    author: Optional[str] = None
    chapter_count: int
    section_count: int
    page_count: int
    word_count: int
    chapters: List[ChapterOutline] = Field(default_factory=list)


# ============================================================
# Location Models (for navigation)
# ============================================================


class PageLocation(BaseModel):
    """Location of a page within the document hierarchy."""

    document_id: UUID
    document_title: str
    chapter_id: UUID
    chapter_title: str
    chapter_index: int
    section_id: UUID
    section_title: str
    section_index: int
    page_id: UUID
    page_number: int


class SearchHit(BaseModel):
    """A search result with location context."""

    chunk_id: UUID
    text: str
    similarity: float
    location: PageLocation
