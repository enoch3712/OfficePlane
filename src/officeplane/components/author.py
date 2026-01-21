"""
AuthorComponent - Agent for writing book-scale documents.

Provides actions for:
- Document/chapter/section/page CRUD
- Semantic search (RAG)
- Navigation and context
- Import from Word documents
- Export to DOCX/PDF
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field

from officeplane.components.action import ComponentAction
from officeplane.components.base import OfficeComponent
from officeplane.components.context import ComponentContext
from officeplane.components.planning import (
    GeneratePlanInput,
    PlanDisplayer,
    PlanGenerator,
    PlanSummary,
    MockPlanLLM,
)
from officeplane.components.runner import LLMProtocol
from officeplane.documents.store import DocumentStore
from officeplane.memory.embeddings import EmbeddingClient
from officeplane.memory.rag import DocumentIndexer, RAGRetriever
from officeplane.memory.vector_store import VectorStore


# ============================================================
# Input/Output Models
# ============================================================


class CreateDocumentInput(BaseModel):
    """Input for creating a new document."""

    title: str = Field(..., description="Title of the document")
    author: Optional[str] = Field(None, description="Author name")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional metadata as key-value pairs"
    )


class DocumentOutput(BaseModel):
    """Output containing document info."""

    id: str = Field(..., description="Document UUID")
    title: str
    author: Optional[str] = None
    created: bool = False


class AddChapterInput(BaseModel):
    """Input for adding a chapter."""

    document_id: str = Field(..., description="Document UUID")
    title: str = Field(..., description="Chapter title")
    order_index: Optional[int] = Field(
        None, description="Position (auto-assigned if not provided)"
    )
    summary: Optional[str] = Field(None, description="Chapter summary")


class ChapterOutput(BaseModel):
    """Output containing chapter info."""

    id: str
    document_id: str
    title: str
    order_index: int


class AddSectionInput(BaseModel):
    """Input for adding a section."""

    chapter_id: str = Field(..., description="Parent chapter UUID")
    title: str = Field(..., description="Section title")
    order_index: Optional[int] = Field(None, description="Position in chapter")


class SectionOutput(BaseModel):
    """Output containing section info."""

    id: str
    chapter_id: str
    title: str
    order_index: int


class WritePageInput(BaseModel):
    """Input for writing a page."""

    section_id: str = Field(..., description="Parent section UUID")
    content: str = Field(..., description="Page content (markdown)")
    page_number: Optional[int] = Field(
        None, description="Page number (auto-assigned if not provided)"
    )


class PageOutput(BaseModel):
    """Output containing page info."""

    id: str
    section_id: str
    page_number: int
    word_count: int
    indexed: bool = False


class EditPageInput(BaseModel):
    """Input for editing a page."""

    page_id: str = Field(..., description="Page UUID to edit")
    content: str = Field(..., description="New page content")


class DeletePageInput(BaseModel):
    """Input for deleting a page."""

    page_id: str = Field(..., description="Page UUID to delete")


class DeleteOutput(BaseModel):
    """Output for delete operations."""

    success: bool
    deleted_id: str


class SearchInput(BaseModel):
    """Input for semantic search."""

    query: str = Field(..., description="Natural language search query")
    top_k: int = Field(5, description="Number of results to return")
    document_id: Optional[str] = Field(
        None, description="Limit search to specific document"
    )


class SearchOutput(BaseModel):
    """Output containing search results."""

    query: str
    results: List[Dict[str, Any]] = Field(
        default_factory=list, description="Search results with text, score, location"
    )
    total: int = 0


class GetOutlineInput(BaseModel):
    """Input for getting document outline."""

    document_id: str = Field(..., description="Document UUID")


class OutlineOutput(BaseModel):
    """Output containing document outline."""

    id: str
    title: str
    author: Optional[str] = None
    chapter_count: int
    section_count: int
    page_count: int
    word_count: int
    chapters: List[Dict[str, Any]] = Field(default_factory=list)


class GetPageInput(BaseModel):
    """Input for getting a page."""

    page_id: str = Field(..., description="Page UUID")


class GetPageOutput(BaseModel):
    """Output containing page content and metadata."""

    id: str
    content: str
    page_number: int
    word_count: int
    location: Optional[Dict[str, Any]] = None


class GetContextInput(BaseModel):
    """Input for getting page context."""

    page_id: str = Field(..., description="Page UUID")
    window: int = Field(1, description="Number of pages before/after to include")


class ContextOutput(BaseModel):
    """Output containing page context."""

    page_id: str
    context: str = ""
    window: int


class ExportDocumentInput(BaseModel):
    """Input for exporting a document."""

    document_id: str = Field(..., description="Document UUID")
    format: str = Field("docx", description="Export format: 'docx' or 'pdf'")


class ExportOutput(BaseModel):
    """Output containing export result."""

    document_id: str
    format: str
    file_url: Optional[str] = None
    success: bool = False
    error: Optional[str] = None


class ImportDocumentInput(BaseModel):
    """Input for importing a Word document."""

    file_path: Optional[str] = Field(
        None, description="Path to .docx file (use this OR content_base64)"
    )
    content_base64: Optional[str] = Field(
        None, description="Base64-encoded .docx content (use this OR file_path)"
    )
    title: Optional[str] = Field(
        None, description="Override document title (uses file title if not provided)"
    )
    author: Optional[str] = Field(None, description="Override author name")
    index_for_search: bool = Field(
        True, description="Whether to index content for semantic search"
    )


class ImportOutput(BaseModel):
    """Output containing import result."""

    document_id: str
    title: str
    author: Optional[str] = None
    chapter_count: int = 0
    section_count: int = 0
    page_count: int = 0
    success: bool = False
    error: Optional[str] = None


class ReimportDocumentInput(BaseModel):
    """Input for re-importing a document to update content."""

    document_id: str = Field(..., description="Existing document UUID to update")
    file_path: Optional[str] = Field(
        None, description="Path to updated .docx file"
    )
    content_base64: Optional[str] = Field(
        None, description="Base64-encoded updated .docx content"
    )
    preserve_structure: bool = Field(
        True, description="Match chapters/sections by title instead of replacing all"
    )


# ============================================================
# AuthorComponent
# ============================================================


class AuthorComponent(OfficeComponent):
    """
    Component for writing and managing book-scale documents.

    Provides document authoring capabilities with:
    - Hierarchical structure (document > chapter > section > page)
    - Semantic search via RAG
    - Export to DOCX/PDF

    Usage:
        author = AuthorComponent()
        ctx = ComponentContext.create()

        # Create a document
        result = await author.execute("create_document", {
            "title": "My Book",
            "author": "AI Author"
        }, ctx)

        # Add structure and content
        chapter = await author.execute("add_chapter", {
            "document_id": result.id,
            "title": "Introduction"
        }, ctx)

        section = await author.execute("add_section", {
            "chapter_id": chapter.id,
            "title": "Getting Started"
        }, ctx)

        page = await author.execute("write_page", {
            "section_id": section.id,
            "content": "This is the beginning..."
        }, ctx)

        # Search
        results = await author.execute("search", {
            "query": "beginning",
            "top_k": 5
        }, ctx)
    """

    def __init__(
        self,
        doc_store: Optional[DocumentStore] = None,
        vector_store: Optional[VectorStore] = None,
        embedding_client: Optional[EmbeddingClient] = None,
        llm: Optional[LLMProtocol] = None,
    ) -> None:
        self._doc_store = doc_store
        self._vector_store = vector_store
        self._embedding_client = embedding_client
        self._llm = llm
        self._indexer: Optional[DocumentIndexer] = None
        self._retriever: Optional[RAGRetriever] = None
        self._plan_generator: Optional[PlanGenerator] = None
        self._connected = False

        super().__init__(
            name="author",
            purpose="Write and manage book-scale documents with chapters, sections, and pages",
            description=(
                "An intelligent document authoring agent that can create, edit, and "
                "search through large documents. Supports hierarchical structure "
                "(document > chapter > section > page), semantic search via RAG, "
                "and export to DOCX/PDF formats."
            ),
        )

    async def _ensure_connected(self) -> None:
        """Ensure all stores are connected."""
        if self._connected:
            return

        if self._doc_store is None:
            self._doc_store = DocumentStore()
        if self._vector_store is None:
            self._vector_store = VectorStore()
        if self._embedding_client is None:
            self._embedding_client = EmbeddingClient()

        await self._doc_store.connect()
        await self._vector_store.connect()

        self._indexer = DocumentIndexer(
            vector_store=self._vector_store,
            embedding_client=self._embedding_client,
        )
        self._retriever = RAGRetriever(
            vector_store=self._vector_store,
            doc_store=self._doc_store,
            embedding_client=self._embedding_client,
        )

        # Initialize plan generator (use mock LLM if none provided)
        plan_llm = self._llm if self._llm else MockPlanLLM()
        self._plan_generator = PlanGenerator(llm=plan_llm)

        self._connected = True

    async def close(self) -> None:
        """Close all connections."""
        if self._doc_store:
            await self._doc_store.close()
        if self._vector_store:
            await self._vector_store.close()
        self._connected = False

    def _build_actions(self) -> None:
        """Build and register all authoring actions."""

        # Create Document
        self._register_action(
            ComponentAction(
                name="create_document",
                description="Create a new document (book-level container)",
                input_model=CreateDocumentInput,
                output_model=DocumentOutput,
                handler=self._create_document,
            )
        )

        # Add Chapter
        self._register_action(
            ComponentAction(
                name="add_chapter",
                description="Add a new chapter to a document",
                input_model=AddChapterInput,
                output_model=ChapterOutput,
                handler=self._add_chapter,
            )
        )

        # Add Section
        self._register_action(
            ComponentAction(
                name="add_section",
                description="Add a new section to a chapter",
                input_model=AddSectionInput,
                output_model=SectionOutput,
                handler=self._add_section,
            )
        )

        # Write Page
        self._register_action(
            ComponentAction(
                name="write_page",
                description="Write content to a new page in a section. Content is automatically indexed for search.",
                input_model=WritePageInput,
                output_model=PageOutput,
                handler=self._write_page,
            )
        )

        # Edit Page
        self._register_action(
            ComponentAction(
                name="edit_page",
                description="Edit an existing page's content. Re-indexes the content for search.",
                input_model=EditPageInput,
                output_model=PageOutput,
                handler=self._edit_page,
            )
        )

        # Delete Page
        self._register_action(
            ComponentAction(
                name="delete_page",
                description="Delete a page and its search index",
                input_model=DeletePageInput,
                output_model=DeleteOutput,
                handler=self._delete_page,
            )
        )

        # Search
        self._register_action(
            ComponentAction(
                name="search",
                description="Semantic search across document content using natural language queries",
                input_model=SearchInput,
                output_model=SearchOutput,
                handler=self._search,
            )
        )

        # Get Outline
        self._register_action(
            ComponentAction(
                name="get_outline",
                description="Get the document outline (table of contents) with chapter/section/page structure",
                input_model=GetOutlineInput,
                output_model=OutlineOutput,
                handler=self._get_outline,
            )
        )

        # Get Page
        self._register_action(
            ComponentAction(
                name="get_page",
                description="Get a page's content and metadata including its location in the document",
                input_model=GetPageInput,
                output_model=GetPageOutput,
                handler=self._get_page,
            )
        )

        # Get Context
        self._register_action(
            ComponentAction(
                name="get_context",
                description="Get surrounding pages for context (useful when editing or continuing writing)",
                input_model=GetContextInput,
                output_model=ContextOutput,
                handler=self._get_context,
            )
        )

        # Export Document
        self._register_action(
            ComponentAction(
                name="export_document",
                description="Export document to DOCX or PDF format",
                input_model=ExportDocumentInput,
                output_model=ExportOutput,
                handler=self._export_document,
            )
        )

        # Import Document
        self._register_action(
            ComponentAction(
                name="import_document",
                description="Import a Word document (.docx) into the document model. Parses headings as chapters/sections.",
                input_model=ImportDocumentInput,
                output_model=ImportOutput,
                handler=self._import_document,
            )
        )

        # Reimport Document
        self._register_action(
            ComponentAction(
                name="reimport_document",
                description="Re-import a Word document to update an existing document. Useful for round-trip editing.",
                input_model=ReimportDocumentInput,
                output_model=ImportOutput,
                handler=self._reimport_document,
            )
        )

        # Generate Plan
        self._register_action(
            ComponentAction(
                name="generate_plan",
                description="Generate an action plan tree for document creation. Returns a structured plan without executing it.",
                input_model=GeneratePlanInput,
                output_model=PlanSummary,
                handler=self._generate_plan,
            )
        )

    # ============================================================
    # Action Handlers
    # ============================================================

    async def _create_document(
        self, ctx: ComponentContext, input_data: CreateDocumentInput
    ) -> DocumentOutput:
        """Create a new document."""
        await self._ensure_connected()
        assert self._doc_store is not None

        doc = await self._doc_store.create_document(
            title=input_data.title,
            author=input_data.author,
            metadata=input_data.metadata,
        )

        ctx.logger.info(f"Created document: {doc.id} - {doc.title}")

        return DocumentOutput(
            id=str(doc.id),
            title=doc.title,
            author=doc.author,
            created=True,
        )

    async def _add_chapter(
        self, ctx: ComponentContext, input_data: AddChapterInput
    ) -> ChapterOutput:
        """Add a chapter to a document."""
        await self._ensure_connected()
        assert self._doc_store is not None

        chapter = await self._doc_store.create_chapter(
            document_id=UUID(input_data.document_id),
            title=input_data.title,
            order_index=input_data.order_index,
            summary=input_data.summary,
        )

        ctx.logger.info(f"Added chapter: {chapter.id} - {chapter.title}")

        return ChapterOutput(
            id=str(chapter.id),
            document_id=str(chapter.document_id),
            title=chapter.title,
            order_index=chapter.order_index,
        )

    async def _add_section(
        self, ctx: ComponentContext, input_data: AddSectionInput
    ) -> SectionOutput:
        """Add a section to a chapter."""
        await self._ensure_connected()
        assert self._doc_store is not None

        section = await self._doc_store.create_section(
            chapter_id=UUID(input_data.chapter_id),
            title=input_data.title,
            order_index=input_data.order_index,
        )

        ctx.logger.info(f"Added section: {section.id} - {section.title}")

        return SectionOutput(
            id=str(section.id),
            chapter_id=str(section.chapter_id),
            title=section.title,
            order_index=section.order_index,
        )

    async def _write_page(
        self, ctx: ComponentContext, input_data: WritePageInput
    ) -> PageOutput:
        """Write a new page and index it for search."""
        await self._ensure_connected()
        assert self._doc_store is not None
        assert self._indexer is not None

        section_id = UUID(input_data.section_id)

        # Create the page
        page = await self._doc_store.create_page(
            section_id=section_id,
            content=input_data.content,
            page_number=input_data.page_number,
        )

        # Get hierarchy for indexing
        chapter_id = await self._doc_store.get_chapter_id_for_section(section_id)
        if chapter_id:
            document_id = await self._doc_store.get_document_id_for_chapter(chapter_id)
        else:
            document_id = None

        # Index the page content
        indexed = False
        if document_id and chapter_id:
            try:
                await self._indexer.index_page(
                    page_id=page.id,
                    document_id=document_id,
                    chapter_id=chapter_id,
                    section_id=section_id,
                    content=input_data.content,
                )
                indexed = True
                ctx.logger.info(f"Indexed page {page.id}")
            except Exception as e:
                ctx.logger.warning(f"Failed to index page: {e}")

        ctx.logger.info(f"Created page: {page.id} (page {page.page_number})")

        return PageOutput(
            id=str(page.id),
            section_id=str(page.section_id),
            page_number=page.page_number,
            word_count=page.word_count,
            indexed=indexed,
        )

    async def _edit_page(
        self, ctx: ComponentContext, input_data: EditPageInput
    ) -> PageOutput:
        """Edit a page and re-index it."""
        await self._ensure_connected()
        assert self._doc_store is not None
        assert self._indexer is not None

        page_id = UUID(input_data.page_id)

        # Update the page
        page = await self._doc_store.update_page(
            page_id=page_id,
            content=input_data.content,
        )

        if not page:
            raise ValueError(f"Page not found: {input_data.page_id}")

        # Get hierarchy for re-indexing
        hierarchy = await self._doc_store.get_page_hierarchy(page_id)

        indexed = False
        if hierarchy:
            document_id, chapter_id, section_id = hierarchy
            try:
                await self._indexer.reindex_page(
                    page_id=page_id,
                    document_id=document_id,
                    chapter_id=chapter_id,
                    section_id=section_id,
                    content=input_data.content,
                )
                indexed = True
                ctx.logger.info(f"Re-indexed page {page_id}")
            except Exception as e:
                ctx.logger.warning(f"Failed to re-index page: {e}")

        ctx.logger.info(f"Updated page: {page_id}")

        return PageOutput(
            id=str(page.id),
            section_id=str(page.section_id),
            page_number=page.page_number,
            word_count=page.word_count,
            indexed=indexed,
        )

    async def _delete_page(
        self, ctx: ComponentContext, input_data: DeletePageInput
    ) -> DeleteOutput:
        """Delete a page and its index."""
        await self._ensure_connected()
        assert self._doc_store is not None
        assert self._indexer is not None

        page_id = UUID(input_data.page_id)

        # Delete index first
        try:
            await self._indexer.delete_page_chunks(page_id)
        except Exception as e:
            ctx.logger.warning(f"Failed to delete page index: {e}")

        # Delete the page
        success = await self._doc_store.delete_page(page_id)

        ctx.logger.info(f"Deleted page: {page_id} (success={success})")

        return DeleteOutput(
            success=success,
            deleted_id=input_data.page_id,
        )

    async def _search(
        self, ctx: ComponentContext, input_data: SearchInput
    ) -> SearchOutput:
        """Semantic search across documents."""
        await self._ensure_connected()
        assert self._retriever is not None

        document_id = UUID(input_data.document_id) if input_data.document_id else None

        hits = await self._retriever.search_to_hits(
            query=input_data.query,
            top_k=input_data.top_k,
            document_id=document_id,
        )

        results = []
        for hit in hits:
            results.append(
                {
                    "chunk_id": str(hit.chunk_id),
                    "text": hit.text,
                    "similarity": hit.similarity,
                    "location": {
                        "document_id": str(hit.location.document_id),
                        "document_title": hit.location.document_title,
                        "chapter_id": str(hit.location.chapter_id),
                        "chapter_title": hit.location.chapter_title,
                        "section_id": str(hit.location.section_id),
                        "section_title": hit.location.section_title,
                        "page_id": str(hit.location.page_id),
                        "page_number": hit.location.page_number,
                    },
                }
            )

        ctx.logger.info(f"Search '{input_data.query}': {len(results)} results")

        return SearchOutput(
            query=input_data.query,
            results=results,
            total=len(results),
        )

    async def _get_outline(
        self, ctx: ComponentContext, input_data: GetOutlineInput
    ) -> OutlineOutput:
        """Get document outline."""
        await self._ensure_connected()
        assert self._doc_store is not None

        outline = await self._doc_store.get_outline(UUID(input_data.document_id))

        if not outline:
            raise ValueError(f"Document not found: {input_data.document_id}")

        chapters = []
        for ch in outline.chapters:
            sections = []
            for sec in ch.sections:
                pages = [
                    {"id": str(p.id), "page_number": p.page_number, "word_count": p.word_count}
                    for p in sec.pages
                ]
                sections.append(
                    {
                        "id": str(sec.id),
                        "title": sec.title,
                        "order_index": sec.order_index,
                        "pages": pages,
                    }
                )
            chapters.append(
                {
                    "id": str(ch.id),
                    "title": ch.title,
                    "order_index": ch.order_index,
                    "summary": ch.summary,
                    "sections": sections,
                }
            )

        return OutlineOutput(
            id=str(outline.id),
            title=outline.title,
            author=outline.author,
            chapter_count=outline.chapter_count,
            section_count=outline.section_count,
            page_count=outline.page_count,
            word_count=outline.word_count,
            chapters=chapters,
        )

    async def _get_page(
        self, ctx: ComponentContext, input_data: GetPageInput
    ) -> GetPageOutput:
        """Get a page's content and location."""
        await self._ensure_connected()
        assert self._doc_store is not None

        page_id = UUID(input_data.page_id)
        page = await self._doc_store.get_page(page_id)

        if not page:
            raise ValueError(f"Page not found: {input_data.page_id}")

        location = await self._doc_store.get_page_location(page_id)
        location_dict = None
        if location:
            location_dict = {
                "document_id": str(location.document_id),
                "document_title": location.document_title,
                "chapter_id": str(location.chapter_id),
                "chapter_title": location.chapter_title,
                "chapter_index": location.chapter_index,
                "section_id": str(location.section_id),
                "section_title": location.section_title,
                "section_index": location.section_index,
            }

        return GetPageOutput(
            id=str(page.id),
            content=page.content,
            page_number=page.page_number,
            word_count=page.word_count,
            location=location_dict,
        )

    async def _get_context(
        self, ctx: ComponentContext, input_data: GetContextInput
    ) -> ContextOutput:
        """Get surrounding pages for context."""
        await self._ensure_connected()
        assert self._doc_store is not None

        page_id = UUID(input_data.page_id)
        context = await self._doc_store.get_surrounding_pages(
            page_id=page_id,
            window=input_data.window,
        )

        return ContextOutput(
            page_id=input_data.page_id,
            context=context or "",
            window=input_data.window,
        )

    async def _export_document(
        self, ctx: ComponentContext, input_data: ExportDocumentInput
    ) -> ExportOutput:
        """Export document to DOCX or PDF."""
        await self._ensure_connected()

        try:
            from officeplane.documents.exporter import DocumentExporter

            exporter = DocumentExporter(doc_store=self._doc_store)
            document_id = UUID(input_data.document_id)

            if input_data.format.lower() == "pdf":
                file_url = await exporter.export_to_pdf(
                    document_id=document_id,
                    ctx=ctx,
                )
            else:
                file_url = await exporter.export_to_docx(
                    document_id=document_id,
                    ctx=ctx,
                )

            return ExportOutput(
                document_id=input_data.document_id,
                format=input_data.format,
                file_url=file_url,
                success=True,
            )

        except ImportError as e:
            return ExportOutput(
                document_id=input_data.document_id,
                format=input_data.format,
                success=False,
                error=f"Export dependencies not installed: {e}",
            )
        except Exception as e:
            ctx.logger.error(f"Export failed: {e}")
            return ExportOutput(
                document_id=input_data.document_id,
                format=input_data.format,
                success=False,
                error=str(e),
            )

    async def _import_document(
        self, ctx: ComponentContext, input_data: ImportDocumentInput
    ) -> ImportOutput:
        """Import a Word document."""
        await self._ensure_connected()

        try:
            from officeplane.documents.importer import DocumentImporter
            import base64

            importer = DocumentImporter(doc_store=self._doc_store)

            # Get document bytes from file or base64
            if input_data.file_path:
                doc = await importer.import_from_file(
                    file_path=input_data.file_path,
                    title=input_data.title,
                    author=input_data.author,
                    index_for_search=input_data.index_for_search,
                )
            elif input_data.content_base64:
                docx_bytes = base64.b64decode(input_data.content_base64)
                doc = await importer.import_from_bytes(
                    docx_bytes=docx_bytes,
                    title=input_data.title,
                    author=input_data.author,
                    index_for_search=input_data.index_for_search,
                )
            else:
                return ImportOutput(
                    document_id="",
                    title="",
                    success=False,
                    error="Either file_path or content_base64 must be provided",
                )

            # Count structure
            chapter_count = len(doc.chapters)
            section_count = sum(len(ch.sections) for ch in doc.chapters)
            page_count = sum(
                len(sec.pages)
                for ch in doc.chapters
                for sec in ch.sections
            )

            ctx.logger.info(
                f"Imported document: {doc.id} - {doc.title} "
                f"({chapter_count} chapters, {section_count} sections, {page_count} pages)"
            )

            return ImportOutput(
                document_id=str(doc.id),
                title=doc.title,
                author=doc.author,
                chapter_count=chapter_count,
                section_count=section_count,
                page_count=page_count,
                success=True,
            )

        except FileNotFoundError as e:
            return ImportOutput(
                document_id="",
                title="",
                success=False,
                error=f"File not found: {e}",
            )
        except ImportError as e:
            return ImportOutput(
                document_id="",
                title="",
                success=False,
                error=f"Import dependencies not installed: {e}",
            )
        except Exception as e:
            ctx.logger.error(f"Import failed: {e}")
            return ImportOutput(
                document_id="",
                title="",
                success=False,
                error=str(e),
            )

    async def _reimport_document(
        self, ctx: ComponentContext, input_data: ReimportDocumentInput
    ) -> ImportOutput:
        """Re-import a Word document to update existing document."""
        await self._ensure_connected()

        try:
            from officeplane.documents.importer import DocumentImporter
            import base64

            importer = DocumentImporter(doc_store=self._doc_store)
            document_id = UUID(input_data.document_id)

            # Get document bytes
            if input_data.file_path:
                with open(input_data.file_path, "rb") as f:
                    docx_bytes = f.read()
            elif input_data.content_base64:
                docx_bytes = base64.b64decode(input_data.content_base64)
            else:
                return ImportOutput(
                    document_id=input_data.document_id,
                    title="",
                    success=False,
                    error="Either file_path or content_base64 must be provided",
                )

            doc = await importer.reimport_document(
                document_id=document_id,
                docx_bytes=docx_bytes,
                preserve_structure=input_data.preserve_structure,
            )

            # Count structure
            chapter_count = len(doc.chapters)
            section_count = sum(len(ch.sections) for ch in doc.chapters)
            page_count = sum(
                len(sec.pages)
                for ch in doc.chapters
                for sec in ch.sections
            )

            ctx.logger.info(
                f"Re-imported document: {doc.id} - {doc.title} "
                f"({chapter_count} chapters, {section_count} sections, {page_count} pages)"
            )

            return ImportOutput(
                document_id=str(doc.id),
                title=doc.title,
                author=doc.author,
                chapter_count=chapter_count,
                section_count=section_count,
                page_count=page_count,
                success=True,
            )

        except FileNotFoundError as e:
            return ImportOutput(
                document_id=input_data.document_id,
                title="",
                success=False,
                error=f"File not found: {e}",
            )
        except ValueError as e:
            return ImportOutput(
                document_id=input_data.document_id,
                title="",
                success=False,
                error=str(e),
            )
        except Exception as e:
            ctx.logger.error(f"Re-import failed: {e}")
            return ImportOutput(
                document_id=input_data.document_id,
                title="",
                success=False,
                error=str(e),
            )

    async def _generate_plan(
        self, ctx: ComponentContext, input_data: GeneratePlanInput
    ) -> PlanSummary:
        """Generate an action plan for document creation."""
        await self._ensure_connected()
        assert self._plan_generator is not None

        ctx.logger.info(f"Generating plan for: {input_data.prompt[:50]}...")

        result = await self._plan_generator.generate_plan(input_data)

        if not result.success:
            raise ValueError(f"Plan generation failed: {result.error}")

        plan = result.plan

        # Generate tree visualization
        tree_viz = PlanDisplayer.to_tree_text(plan)

        ctx.logger.info(
            f"Generated plan: {plan.title} "
            f"({plan.total_nodes} actions, {result.generation_time_ms}ms)"
        )

        return PlanSummary.from_plan(plan)
