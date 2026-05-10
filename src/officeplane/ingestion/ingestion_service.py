"""Vision-based document ingestion service.

Orchestrates the full pipeline from document upload to structured storage:
1. Format detection (PDF/DOCX/etc.)
2. Conversion to PDF if needed (via LibreOffice driver)
3. PDF to page images (via PyMuPDF)
4. Image compression (via Pillow)
5. Vision model analysis (batched)
6. Structure parsing to document models
7. Storage in PostgreSQL
8. Optional RAG indexing
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

            # Step 2: Convert to PDF if needed
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
        """Merge batched page results into a document structure."""
        # Collect all pages with their structure hints
        all_pages: List[Dict[str, Any]] = []

        for batch in batch_results:
            pages = batch.get("pages", [])
            all_pages.extend(pages)

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

            # Check for new chapter
            if chapter_title:
                if current_chapter:
                    if current_section:
                        current_chapter["sections"].append(current_section)
                    chapters.append(current_chapter)

                current_chapter = {
                    "title": chapter_title,
                    "summary": None,
                    "sections": [],
                }
                current_section = None

            # Check for new section
            if section_title:
                if current_section and current_chapter:
                    current_chapter["sections"].append(current_section)

                current_section = {
                    "title": section_title,
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
                    "pages": [],
                }

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

        return {
            "title": "Document",
            "author": None,
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

        # Create chapters, sections, and pages
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
                    await self._doc_store.create_page(
                        section_id=db_section.id,
                        content=page.content,
                        page_number=page.page_number,
                    )

        return await self._doc_store.get_document(db_doc.id, load_children=True)

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
