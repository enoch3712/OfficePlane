"""Document ingestion service.

Supports two modes:
- text (default): extract text directly (PDF/DOCX/PPTX) then structure via DeepSeek.
- vision: render pages to images and analyze with a vision model (Gemini/mock).

Orchestrates the full pipeline from document upload to structured storage:
1. Format detection (PDF/DOCX/etc.)
2. [text mode] Text extraction per page/slide
3. [text mode] Structure analysis via DeepSeek LLM
4. [vision mode] Conversion to PDF if needed (via LibreOffice driver)
5. [vision mode] PDF to page images (via PyMuPDF)
6. [vision mode] Image compression (via Pillow)
7. [vision mode] Vision model analysis (batched)
8. Structure parsing to document models
9. Storage in PostgreSQL
10. Optional RAG indexing
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
from uuid import UUID, uuid4

from officeplane.core.render import PageImage, pdf_to_images
from officeplane.documents.models import DocumentModel
from officeplane.documents.store import DocumentStore
from officeplane.drivers.base import OfficeDriver
from officeplane.ingestion.config import IngestionConfig
from officeplane.ingestion.format_detector import (
    DocumentFormat,
    detect_format,
    is_pdf,
    needs_conversion,
)
from officeplane.ingestion.image_processor import ImageProcessor
from officeplane.ingestion.prompts import SYSTEM_PROMPT, get_structure_prompt
from officeplane.ingestion.structure_parser import StructureParser
from officeplane.ingestion.vision_protocol import VisionModelProtocol, VisionResponse

log = logging.getLogger("officeplane.ingestion")


# Progress callback type
ProgressCallback = Callable[[str, int, int], None]


async def embed_pending_chunks(db: Any, document_id: str, batch_size: int = 16) -> int:
    """Embed all NULL-embedding chunks for a document using the configured provider.

    Args:
        db: A connected Prisma client instance.
        document_id: UUID string of the document whose chunks need embedding.
        batch_size: Number of chunks to process per batch.

    Returns:
        Number of chunks embedded.
    """
    from officeplane.memory.embedding_provider import get_embedding_provider

    try:
        provider = get_embedding_provider()
    except Exception as exc:
        log.warning("Embedding provider unavailable — skipping chunk embedding: %s", exc)
        return 0

    inserted = 0
    while True:
        rows = await db.query_raw(
            "SELECT id, text FROM chunks WHERE document_id = $1::uuid AND embedding IS NULL LIMIT $2",
            document_id,
            batch_size,
        )
        if not rows:
            break
        texts = [r["text"] for r in rows]
        try:
            embeddings = await provider.embed_batch(texts)
        except Exception as exc:
            log.warning("embed_batch failed for document %s: %s", document_id, exc)
            break
        for r, emb in zip(rows, embeddings):
            vec_str = "[" + ",".join(f"{x:.7f}" for x in emb) + "]"
            await db.execute_raw(
                "UPDATE chunks SET embedding = $1::vector WHERE id = $2::uuid",
                vec_str,
                r["id"],
            )
            inserted += 1
    if inserted:
        log.info("Embedded %d chunks for document %s", inserted, document_id)
    return inserted


@dataclass
class IngestionResult:
    """Result of document ingestion.

    Attributes:
        success: Whether ingestion completed successfully.
        document_id: UUID of the created document (if successful).
        document: Full document model (if successful).
        chapter_count: Number of chapters extracted.
        section_count: Number of sections extracted.
        page_count: Number of pages processed.
        error: Error message (if failed).
        metadata: Additional metadata about the ingestion.
    """

    success: bool
    document_id: Optional[UUID] = None
    document: Optional[DocumentModel] = None
    chapter_count: int = 0
    section_count: int = 0
    page_count: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class VisionIngestionService:
    """Orchestrates vision-based document ingestion.

    Uses vision models to extract document structure from page images,
    enabling accurate chapter/section/page extraction from any document.
    """

    def __init__(
        self,
        driver: Optional[OfficeDriver] = None,
        doc_store: Optional[DocumentStore] = None,
        vision_adapter: Optional[VisionModelProtocol] = None,
        config: Optional[IngestionConfig] = None,
    ):
        """Initialize the ingestion service.

        Args:
            driver: Office driver for DOCX→PDF conversion.
            doc_store: Document store for persistence.
            vision_adapter: Vision model adapter. If not provided,
                one will be created based on config.
            config: Ingestion configuration. If not provided,
                defaults will be loaded from environment.
        """
        self._driver = driver
        self._doc_store = doc_store
        self._config = config or IngestionConfig()
        self._vision_adapter = vision_adapter
        self._image_processor: Optional[ImageProcessor] = None
        self._connected = False

    async def connect(self) -> None:
        """Initialize connections and adapters."""
        if self._connected:
            return

        # Initialize image processor
        self._image_processor = ImageProcessor(
            target_size_kb=self._config.image_size_kb,
        )

        # Initialize vision adapter if not provided
        if self._vision_adapter is None:
            self._vision_adapter = self._create_vision_adapter()

        # Connect to document store if provided
        if self._doc_store:
            await self._doc_store.connect()

        self._connected = True
        log.info(
            "Ingestion service connected",
            extra={
                "vision_provider": self._config.vision_provider,
                "vision_model": self._config.vision_model,
            },
        )

    async def close(self) -> None:
        """Close connections."""
        if self._doc_store:
            await self._doc_store.close()
        self._connected = False

    def _create_vision_adapter(self) -> VisionModelProtocol:
        """Create vision adapter based on configuration."""
        if self._config.vision_provider == "mock":
            from officeplane.ingestion.vision_adapters.mock import MockVisionAdapter

            return MockVisionAdapter()

        if self._config.vision_provider == "gemini":
            from officeplane.ingestion.vision_adapters.gemini import GeminiVisionAdapter

            if not self._config.google_api_key:
                raise ValueError(
                    "GOOGLE_API_KEY is required for Gemini vision adapter. "
                    "Set it in environment or config."
                )

            return GeminiVisionAdapter(
                api_key=self._config.google_api_key,
                model=self._config.vision_model,
                max_images=self._config.max_images_per_call,
            )

        raise ValueError(f"Unknown vision provider: {self._config.vision_provider}")

    async def ingest(
        self,
        data: bytes,
        filename: str,
        progress_callback: Optional[ProgressCallback] = None,
        document_id: Optional[UUID] = None,
    ) -> IngestionResult:
        """Ingest a document and extract its structure.

        Args:
            data: Document bytes (PDF or Office document).
            filename: Original filename (used for format detection).
            progress_callback: Optional callback for progress updates.
                Receives (stage, current, total).
            document_id: Optional UUID to use for the document.

        Returns:
            IngestionResult with the extracted document structure.
        """
        if not self._connected:
            await self.connect()

        document_id = document_id or uuid4()

        try:
            # Step 1: Detect format
            self._report_progress(progress_callback, "detecting_format", 0, 1)
            doc_format = detect_format(data, filename)
            log.info(f"Detected format: {doc_format.value} for {filename}")

            if doc_format == DocumentFormat.UNKNOWN:
                return IngestionResult(
                    success=False,
                    error=f"Unknown document format for {filename}",
                )

            # Branch: text mode (default) vs vision mode
            if self._config.mode == "text":
                return await self._ingest_text(
                    data, filename, doc_format, document_id, progress_callback
                )

            # Step 2: Convert to PDF if needed (vision path)
            pdf_bytes = data
            if needs_conversion(data, filename):
                self._report_progress(progress_callback, "converting_to_pdf", 0, 1)
                pdf_bytes = await self._convert_to_pdf(data, filename)
                if pdf_bytes is None:
                    return IngestionResult(
                        success=False,
                        error="Failed to convert document to PDF",
                    )
                log.info(f"Converted {filename} to PDF ({len(pdf_bytes)} bytes)")

            # Step 3: Render to images
            self._report_progress(progress_callback, "rendering_pages", 0, 1)
            page_images = pdf_to_images(pdf_bytes, dpi=self._config.pdf_dpi, fmt="png")
            total_pages = len(page_images)
            log.info(f"Rendered {total_pages} pages from PDF")

            if total_pages == 0:
                return IngestionResult(
                    success=False,
                    error="Document has no pages",
                )

            # Step 4: Compress images
            self._report_progress(progress_callback, "compressing_images", 0, total_pages)
            compressed_images = await self._compress_images(
                page_images, progress_callback
            )
            log.info(f"Compressed {len(compressed_images)} images")

            # Step 5: Analyze with vision model
            self._report_progress(progress_callback, "analyzing_structure", 0, total_pages)
            structure_data, page_contents = await self._analyze_with_vision(
                compressed_images, progress_callback
            )

            if structure_data is None:
                return IngestionResult(
                    success=False,
                    error="Failed to analyze document structure",
                )

            # Step 6: Parse into document model
            self._report_progress(progress_callback, "parsing_structure", 0, 1)
            parser = StructureParser(document_id=document_id)
            parse_result = parser.parse_full_response(structure_data, page_contents)

            if not parse_result.success or parse_result.document is None:
                return IngestionResult(
                    success=False,
                    error=f"Failed to parse document structure: {parse_result.errors}",
                )

            document = parse_result.document

            # Step 7: Store in database
            if self._doc_store:
                self._report_progress(progress_callback, "storing_document", 0, 1)
                stored_document = await self._store_document(document)
                if stored_document is not None:
                    document = stored_document
                log.info(f"Stored document {document.id} with {document.chapter_count} chapters")

            # Step 8: Index for RAG (if enabled)
            if self._config.auto_index and self._doc_store:
                self._report_progress(progress_callback, "indexing", 0, 1)
                # RAG indexing would go here
                # await self._index_for_rag(document)

            self._report_progress(progress_callback, "complete", 1, 1)

            return IngestionResult(
                success=True,
                document_id=document.id,
                document=document,
                chapter_count=document.chapter_count,
                section_count=document.section_count,
                page_count=document.page_count,
                metadata={
                    "original_format": doc_format.value,
                    "filename": filename,
                    "vision_model": self._config.vision_model,
                },
            )

        except Exception as e:
            log.exception(f"Ingestion failed for {filename}")
            return IngestionResult(
                success=False,
                error=str(e),
            )

    async def _ingest_text(
        self,
        data: bytes,
        filename: str,
        doc_format: DocumentFormat,
        document_id: UUID,
        progress_callback: Optional[ProgressCallback],
    ) -> "IngestionResult":
        """Text-based ingestion: extract text per page then structure via DeepSeek."""
        from officeplane.ingestion.structure_adapters import DeepSeekStructureAdapter
        from officeplane.ingestion.text_extractors import extract_text

        # Legacy binaries (DOC, PPT) can't be parsed directly — convert to PDF first.
        working_data = data
        working_format = doc_format
        if doc_format in (DocumentFormat.DOC, DocumentFormat.PPT):
            if self._driver is None:
                return IngestionResult(
                    success=False,
                    error="No driver available for legacy format conversion",
                )
            self._report_progress(progress_callback, "converting_to_pdf", 0, 1)
            pdf_bytes = await self._convert_to_pdf(data, filename)
            if pdf_bytes is None:
                return IngestionResult(
                    success=False,
                    error="Failed to convert legacy format to PDF",
                )
            working_data = pdf_bytes
            working_format = DocumentFormat.PDF

        self._report_progress(progress_callback, "extracting_text", 0, 1)
        try:
            pages = extract_text(working_data, working_format)
        except Exception as e:
            log.error(f"Text extraction failed for {filename}: {e}")
            return IngestionResult(success=False, error=f"Text extraction failed: {e}")

        if not pages:
            return IngestionResult(success=False, error="No text extracted from document")

        log.info(f"Extracted text from {len(pages)} pages of {filename}")

        self._report_progress(progress_callback, "structuring", 0, len(pages))
        adapter = DeepSeekStructureAdapter(
            model=self._config.ingestion_model,
            max_pages_per_call=max(self._config.batch_size, 1) * 8,  # larger chunks for text
        )
        try:
            structure_data = await adapter.analyze(pages, filename=filename)
        except Exception as e:
            log.error(f"DeepSeek structuring failed for {filename}: {e}")
            return IngestionResult(success=False, error=f"Structuring failed: {e}")

        # Support both "text" (legacy extractors) and "content" (OCR-aware pdf extractor)
        page_contents = {p["page_number"]: p.get("content") or p.get("text", "") for p in pages}

        self._report_progress(progress_callback, "parsing_structure", 0, 1)
        parser = StructureParser(document_id=document_id)
        parse_result = parser.parse_full_response(structure_data, page_contents)

        if not parse_result.success or parse_result.document is None:
            return IngestionResult(
                success=False,
                error=f"Failed to parse document structure: {parse_result.errors}",
            )

        document = parse_result.document

        if self._doc_store:
            self._report_progress(progress_callback, "storing_document", 0, 1)
            stored = await self._store_document(document)
            if stored is not None:
                document = stored
            log.info(
                f"Stored document {document.id} with {document.chapter_count} chapters"
            )

        self._report_progress(progress_callback, "complete", 1, 1)
        return IngestionResult(
            success=True,
            document_id=document.id,
            document=document,
            chapter_count=document.chapter_count,
            section_count=document.section_count,
            page_count=document.page_count,
            metadata={
                "original_format": doc_format.value,
                "filename": filename,
                "ingestion_model": self._config.ingestion_model,
                "mode": "text",
            },
        )

    async def _convert_to_pdf(self, data: bytes, filename: str) -> Optional[bytes]:
        """Convert document to PDF using the office driver."""
        if self._driver is None:
            log.error("No office driver available for conversion")
            return None

        try:
            # Run synchronous conversion in thread pool
            loop = asyncio.get_event_loop()
            pdf_bytes = await loop.run_in_executor(
                None,
                lambda: self._driver.convert_to_pdf(filename, data),
            )
            return pdf_bytes
        except Exception as e:
            log.error(f"PDF conversion failed: {e}")
            return None

    async def _compress_images(
        self,
        page_images: List[PageImage],
        progress_callback: Optional[ProgressCallback],
    ) -> List[bytes]:
        """Compress page images for vision model consumption."""
        if self._image_processor is None:
            raise RuntimeError("Image processor not initialized")

        compressed = []
        total = len(page_images)

        for i, page_image in enumerate(page_images):
            self._report_progress(progress_callback, "compressing_images", i, total)

            # Run compression in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                None,
                lambda img=page_image: self._image_processor.process(img.data),
            )
            compressed.append(result.data)

        return compressed

    async def _analyze_with_vision(
        self,
        images: List[bytes],
        progress_callback: Optional[ProgressCallback],
    ) -> tuple[Optional[Dict[str, Any]], Dict[int, str]]:
        """Analyze images with vision model to extract structure.

        Returns:
            Tuple of (structure_data, page_contents).
        """
        if self._vision_adapter is None:
            raise RuntimeError("Vision adapter not initialized")

        total_pages = len(images)
        batch_size = min(self._config.batch_size, self._vision_adapter.max_images_per_call)

        # If document fits in one batch, use single-shot extraction
        if total_pages <= batch_size:
            return await self._analyze_single_batch(images, progress_callback)

        # Otherwise use batched extraction
        return await self._analyze_batched(images, batch_size, progress_callback)

    async def _analyze_single_batch(
        self,
        images: List[bytes],
        progress_callback: Optional[ProgressCallback],
    ) -> tuple[Optional[Dict[str, Any]], Dict[int, str]]:
        """Analyze all pages in a single vision call."""
        self._report_progress(progress_callback, "analyzing_structure", 0, len(images))

        prompt = get_structure_prompt(
            start_page=1,
            end_page=len(images),
            batch_number=1,
            total_batches=1,
        )

        response = await self._vision_adapter.analyze_images(
            images=images,
            prompt=prompt,
            system_prompt=SYSTEM_PROMPT,
            start_page=1,
        )

        if not response.success:
            log.error(f"Vision analysis failed: {response.error}")
            return None, {}

        # Extract page contents from response
        page_contents: Dict[int, str] = {}
        if response.json_data:
            chapters = response.json_data.get("chapters", [])
            for chapter in chapters:
                for section in chapter.get("sections", []):
                    for page in section.get("pages", []):
                        if isinstance(page, dict):
                            page_num = page.get("page_number", 0)
                            content = page.get("content", "")
                            if page_num and content:
                                page_contents[page_num] = content

        self._report_progress(
            progress_callback, "analyzing_structure", len(images), len(images)
        )

        return response.json_data, page_contents

    async def _analyze_batched(
        self,
        images: List[bytes],
        batch_size: int,
        progress_callback: Optional[ProgressCallback],
    ) -> tuple[Optional[Dict[str, Any]], Dict[int, str]]:
        """Analyze pages in batches and merge results."""
        total_pages = len(images)
        num_batches = (total_pages + batch_size - 1) // batch_size

        batch_results: List[Dict[str, Any]] = []
        page_contents: Dict[int, str] = {}
        pages_processed = 0

        for batch_idx in range(num_batches):
            start_idx = batch_idx * batch_size
            end_idx = min(start_idx + batch_size, total_pages)
            batch_images = images[start_idx:end_idx]

            self._report_progress(
                progress_callback, "analyzing_structure", pages_processed, total_pages
            )

            # start_page is 1-indexed
            start_page = start_idx + 1
            prompt = get_structure_prompt(
                start_page=start_page,
                end_page=end_idx,
                batch_number=batch_idx + 1,
                total_batches=num_batches,
            )

            response = await self._vision_adapter.analyze_images(
                images=batch_images,
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
                start_page=start_page,
            )

            if not response.success:
                log.warning(
                    f"Batch {batch_idx + 1}/{num_batches} failed: {response.error}"
                )
                continue

            if response.json_data:
                json_data = response.json_data

                # Handle case where API returns a list directly
                if isinstance(json_data, list):
                    json_data = {"pages": json_data}

                # Normalize response: extract pages from chapters if no top-level pages
                normalized = self._normalize_batch_response(json_data, start_page, end_idx)
                batch_results.append(normalized)

                # Extract page contents from normalized pages array
                pages = normalized.get("pages", [])
                if isinstance(pages, list):
                    for page in pages:
                        if isinstance(page, dict):
                            page_num = page.get("page_number", 0)
                            content = page.get("content", "")
                            if page_num and content:
                                page_contents[page_num] = content

            pages_processed = end_idx

        if not batch_results:
            return None, {}

        # Merge batch results into document structure
        merged = self._merge_batch_results(batch_results)

        self._report_progress(
            progress_callback, "analyzing_structure", total_pages, total_pages
        )

        return merged, page_contents

    def _normalize_batch_response(
        self,
        json_data: Dict[str, Any],
        start_page: int,
        end_page: int,
    ) -> Dict[str, Any]:
        """Normalize batch response to ensure pages array exists.

        Handles cases where the model returns a chapters structure
        instead of the expected flat pages array.

        Args:
            json_data: Raw response from vision model.
            start_page: Expected start page for this batch.
            end_page: Expected end page for this batch.

        Returns:
            Normalized response with pages array.
        """
        # If pages array exists at top level, return as-is
        if "pages" in json_data and isinstance(json_data["pages"], list):
            return json_data

        # Extract pages from chapters structure if present
        pages: List[Dict[str, Any]] = []

        chapters = json_data.get("chapters", [])
        if chapters:
            for chapter in chapters:
                chapter_title = chapter.get("title")
                for section in chapter.get("sections", []):
                    section_title = section.get("title")
                    for page in section.get("pages", []):
                        if isinstance(page, dict):
                            page_entry = {
                                "page_number": page.get("page_number", 0),
                                "content": page.get("content", ""),
                                "chapter_title": chapter_title if page.get("page_number") == start_page else None,
                                "section_title": section_title,
                            }
                            pages.append(page_entry)
                        elif isinstance(page, int):
                            # Page is just a page number
                            page_entry = {
                                "page_number": page,
                                "content": "",
                                "chapter_title": chapter_title if page == start_page else None,
                                "section_title": section_title,
                            }
                            pages.append(page_entry)

        # If we still have no pages, create placeholder entries
        if not pages:
            log.warning(
                f"No pages found in batch response for pages {start_page}-{end_page}, "
                f"creating placeholders. Response keys: {list(json_data.keys())}"
            )
            for page_num in range(start_page, end_page + 1):
                pages.append({
                    "page_number": page_num,
                    "content": "",
                    "chapter_title": None,
                    "section_title": None,
                })

        return {"pages": pages}

    def _merge_batch_results(
        self, batch_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Merge batched page results into a document structure.

        Captures document- and chapter-level metadata that any single batch
        emits (title, author, document_summary, topics, key_entities, plus
        per-page chapter_summary / section_summary) so the merged dict the
        parser sees mirrors the shape ``parse_full_response`` expects.
        """
        # Document-level metadata: take the first non-empty value across batches.
        title: Optional[str] = None
        author: Optional[str] = None
        document_summary: Optional[str] = None
        topics: List[str] = []
        seen_topics: set[str] = set()
        key_entities: Dict[str, List[Any]] = {}

        for batch in batch_results:
            if title is None and batch.get("title"):
                title = batch["title"]
            if author is None and batch.get("author"):
                author = batch["author"]
            if document_summary is None and batch.get("document_summary"):
                document_summary = batch["document_summary"]
            for tag in batch.get("topics", []) or []:
                if isinstance(tag, str) and tag and tag not in seen_topics:
                    seen_topics.add(tag)
                    topics.append(tag)
            for ent_key, values in (batch.get("key_entities", {}) or {}).items():
                if not isinstance(values, list):
                    continue
                bucket = key_entities.setdefault(ent_key, [])
                for v in values:
                    if v not in bucket:
                        bucket.append(v)

        # Collect all pages with their structure hints
        all_pages: List[Dict[str, Any]] = []
        for batch in batch_results:
            for page in batch.get("pages", []):
                all_pages.append(page)

        # Sort by page number
        all_pages.sort(key=lambda p: p.get("page_number", 0))

        # Build document structure from page annotations
        chapters: List[Dict[str, Any]] = []
        current_chapter: Optional[Dict[str, Any]] = None
        current_section: Optional[Dict[str, Any]] = None

        for page in all_pages:
            page_num = page.get("page_number", 0)
            content = page.get("content", "")
            chapter_title = page.get("chapter_title")
            section_title = page.get("section_title")
            chapter_summary = page.get("chapter_summary") or page.get("chapter_overview")
            section_summary = page.get("section_summary") or page.get("section_overview")

            # Check for new chapter
            if chapter_title:
                if current_chapter:
                    if current_section:
                        current_chapter["sections"].append(current_section)
                    chapters.append(current_chapter)

                current_chapter = {
                    "title": chapter_title,
                    "summary": chapter_summary,
                    "sections": [],
                }
                current_section = None

            # Check for new section
            if section_title:
                if current_section and current_chapter:
                    current_chapter["sections"].append(current_section)

                current_section = {
                    "title": section_title,
                    "summary": section_summary,
                    "pages": [],
                }

            # Ensure we have a chapter and section
            if not current_chapter:
                current_chapter = {
                    "title": "Main Content",
                    "summary": None,
                    "sections": [],
                }

            if not current_section:
                current_section = {
                    "title": "Content",
                    "summary": None,
                    "pages": [],
                }

            # Promote a late-arriving chapter summary onto the current chapter
            if chapter_summary and not current_chapter.get("summary"):
                current_chapter["summary"] = chapter_summary
            if section_summary and not current_section.get("summary"):
                current_section["summary"] = section_summary

            # Add page
            current_section["pages"].append({
                "page_number": page_num,
                "content": content,
            })

        # Finalize
        if current_section and current_chapter:
            current_chapter["sections"].append(current_section)
        if current_chapter:
            chapters.append(current_chapter)

        # Document title fallback: prefer top-level title; else first chapter title; else "Document"
        if not title and chapters:
            title = chapters[0].get("title")
        return {
            "title": title or "Document",
            "author": author,
            "document_summary": document_summary,
            "topics": topics,
            "key_entities": key_entities,
            "chapters": chapters,
        }

    async def _store_document(self, document: DocumentModel) -> Optional[DocumentModel]:
        """Store document and its hierarchy in the database."""
        if not self._doc_store:
            return None

        # Create document
        db_doc = await self._doc_store.create_document(
            title=document.title,
            author=document.author,
            metadata=document.metadata,
            summary=document.summary,
            topics=document.topics,
            key_entities=document.key_entities,
        )

        # Create chapters, sections, and pages; also insert page-level chunks for RAG.
        page_chunk_rows: list[dict] = []  # collect (document_id, chapter_id, section_id, page_id, text)
        for chapter in document.chapters:
            db_chapter = await self._doc_store.create_chapter(
                document_id=db_doc.id,
                title=chapter.title,
                order_index=chapter.order_index,
                summary=chapter.summary,
            )

            for section in chapter.sections:
                db_section = await self._doc_store.create_section(
                    chapter_id=db_chapter.id,
                    title=section.title,
                    order_index=section.order_index,
                    summary=section.summary,
                )

                for page in section.pages:
                    db_page = await self._doc_store.create_page(
                        section_id=db_section.id,
                        content=page.content,
                        page_number=page.page_number,
                    )
                    if page.content and page.content.strip():
                        page_chunk_rows.append({
                            "document_id": str(db_doc.id),
                            "chapter_id": str(db_chapter.id),
                            "section_id": str(db_section.id),
                            "page_id": str(db_page.id) if db_page else None,
                            "text": page.content,
                        })

        # Insert page-level chunks (without embeddings — embeddings are filled later).
        if page_chunk_rows:
            await self._insert_page_chunks(page_chunk_rows)

        # Embed all newly inserted chunks asynchronously.
        try:
            from prisma import Prisma
            db = Prisma()
            await db.connect()
            try:
                n = await embed_pending_chunks(db, str(db_doc.id))
                if n:
                    log.info("Embedded %d chunks for new document %s", n, db_doc.id)
            finally:
                await db.disconnect()
        except Exception as exc:
            log.warning("Post-ingestion embedding step failed (non-fatal): %s", exc)

        return await self._doc_store.get_document(db_doc.id, load_children=True)

    async def _insert_page_chunks(self, rows: list[dict]) -> None:
        """Insert page-level chunk records (no embedding) using raw asyncpg."""
        import os
        import asyncpg

        database_url = os.getenv(
            "DATABASE_URL", "postgresql://officeplane:officeplane@db:5432/officeplane"
        )
        conn = await asyncpg.connect(database_url)
        try:
            for r in rows:
                text = r["text"]
                await conn.execute(
                    """
                    INSERT INTO chunks
                        (document_id, chapter_id, section_id, page_id, text,
                         start_offset, end_offset, token_count)
                    VALUES ($1::uuid, $2::uuid, $3::uuid, $4::uuid, $5, 0, $6, 0)
                    """,
                    r["document_id"],
                    r["chapter_id"],
                    r["section_id"],
                    r["page_id"],
                    text,
                    len(text),
                )
        except Exception as exc:
            log.warning("Chunk insertion failed (non-fatal): %s", exc)
        finally:
            await conn.close()

    def _report_progress(
        self,
        callback: Optional[ProgressCallback],
        stage: str,
        current: int,
        total: int,
    ) -> None:
        """Report progress via callback if provided."""
        if callback:
            try:
                callback(stage, current, total)
            except Exception as e:
                log.warning(f"Progress callback failed: {e}")
