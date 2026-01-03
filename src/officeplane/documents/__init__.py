"""
Document authoring domain.

Provides document modeling, storage, and chunking for book-scale documents.
"""

from officeplane.documents.models import (
    ChapterModel,
    ChapterOutline,
    ChunkModel,
    DocumentModel,
    DocumentOutline,
    PageLocation,
    PageModel,
    PageOutline,
    SearchHit,
    SectionModel,
    SectionOutline,
)
from officeplane.documents.chunker import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DEFAULT_MIN_CHUNK_SIZE,
    SlidingWindowChunker,
    TextChunk,
    chunk_text,
    get_chunker,
)
from officeplane.documents.store import DocumentStore
from officeplane.documents.exporter import DocumentExporter
from officeplane.documents.importer import (
    DocumentImporter,
    DocumentEditor,
    ParsedDocument,
    ParsedChapter,
    ParsedSection,
    import_document,
)

__all__ = [
    # Models
    "DocumentModel",
    "ChapterModel",
    "SectionModel",
    "PageModel",
    "ChunkModel",
    # Outline models
    "DocumentOutline",
    "ChapterOutline",
    "SectionOutline",
    "PageOutline",
    # Location/Search models
    "PageLocation",
    "SearchHit",
    # Chunker
    "SlidingWindowChunker",
    "TextChunk",
    "chunk_text",
    "get_chunker",
    "DEFAULT_CHUNK_SIZE",
    "DEFAULT_CHUNK_OVERLAP",
    "DEFAULT_MIN_CHUNK_SIZE",
    # Store
    "DocumentStore",
    # Exporter
    "DocumentExporter",
    # Importer
    "DocumentImporter",
    "DocumentEditor",
    "ParsedDocument",
    "ParsedChapter",
    "ParsedSection",
    "import_document",
]
