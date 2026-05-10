"""Parser for converting vision model JSON output to document models."""

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from officeplane.documents.models import (
    ChapterModel,
    DocumentModel,
    PageModel,
    SectionModel,
)


@dataclass
class ParsedPage:
    """Intermediate representation of a parsed page."""

    page_number: int
    content: str
    chapter_title: Optional[str] = None
    section_title: Optional[str] = None


@dataclass
class ParseResult:
    """Result of parsing vision model output."""

    document: Optional[DocumentModel] = None
    pages_parsed: int = 0
    chapters_found: int = 0
    sections_found: int = 0
    errors: List[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        """Whether parsing was successful."""
        return self.document is not None and not self.errors


class StructureParser:
    """Parses vision model JSON output into document models."""

    def __init__(self, document_id: Optional[UUID] = None):
        """Initialize the parser.

        Args:
            document_id: Optional UUID to use for the document.
                If not provided, a new UUID will be generated.
        """
        self._document_id = document_id or uuid4()

    def parse_full_response(
        self,
        json_data: Dict[str, Any],
        page_contents: Optional[Dict[int, str]] = None,
    ) -> ParseResult:
        """Parse a complete document structure response.

        Handles the format from STRUCTURE_EXTRACTION_PROMPT.

        Args:
            json_data: JSON response from vision model.
            page_contents: Optional mapping of page numbers to content
                for pages not included in the JSON.

        Returns:
            ParseResult with document model.
        """
        errors = []
        page_contents = page_contents or {}

        # Extract document metadata
        title = json_data.get("title", "Untitled Document")
        author = json_data.get("author")

        # Parse chapters
        chapters_data = json_data.get("chapters", [])
        if not chapters_data:
            errors.append("No chapters found in response")
            return ParseResult(errors=errors)

        chapters = []
        total_pages = 0
        total_sections = 0

        for chapter_idx, chapter_data in enumerate(chapters_data):
            chapter_id = uuid4()
            chapter_title = chapter_data.get("title", f"Chapter {chapter_idx + 1}")
            chapter_summary = chapter_data.get("summary")

            # Parse sections
            sections_data = chapter_data.get("sections", [])
            if not sections_data:
                # Create default section if none exist
                sections_data = [{
                    "title": "Main Content",
                    "pages": chapter_data.get("pages", []),
                }]

            sections = []
            for section_idx, section_data in enumerate(sections_data):
                section_id = uuid4()
                section_title = section_data.get("title", f"Section {section_idx + 1}")

                # Parse pages
                pages_data = section_data.get("pages", [])
                pages = []

                for page_data in pages_data:
                    if isinstance(page_data, int):
                        # Just page number, get content from page_contents
                        page_number = page_data
                        content = page_contents.get(page_number, "")
                    elif isinstance(page_data, dict):
                        # Full page object
                        page_number = page_data.get("page_number", 0)
                        content = page_data.get("content", "")
                    else:
                        continue

                    page = PageModel(
                        id=uuid4(),
                        section_id=section_id,
                        page_number=page_number,
                        content=content,
                    )
                    page.update_word_count()
                    pages.append(page)
                    total_pages += 1

                section_summary = section_data.get("summary")

                section = SectionModel(
                    id=section_id,
                    chapter_id=chapter_id,
                    title=section_title,
                    order_index=section_idx,
                    summary=section_summary,
                    pages=pages,
                )
                sections.append(section)
                total_sections += 1

            chapter = ChapterModel(
                id=chapter_id,
                document_id=self._document_id,
                title=chapter_title,
                order_index=chapter_idx,
                summary=chapter_summary,
                sections=sections,
            )
            chapters.append(chapter)

        document = DocumentModel(
            id=self._document_id,
            title=title,
            author=author,
            summary=json_data.get("document_summary"),
            topics=list(json_data.get("topics", []) or []),
            key_entities=dict(json_data.get("key_entities", {}) or {}),
            chapters=chapters,
        )

        return ParseResult(
            document=document,
            pages_parsed=total_pages,
            chapters_found=len(chapters),
            sections_found=total_sections,
            errors=errors,
        )

    def parse_batch_responses(
        self,
        batch_results: List[Dict[str, Any]],
        page_contents: Dict[int, str],
    ) -> ParseResult:
        """Parse batch responses and merge into document structure.

        Handles the format from BATCH_STRUCTURE_PROMPT.

        Args:
            batch_results: List of JSON responses from batched vision calls.
            page_contents: Mapping of page numbers to content.

        Returns:
            ParseResult with merged document model.
        """
        errors = []

        # Collect all pages with their structure hints
        all_pages: List[ParsedPage] = []

        for batch_data in batch_results:
            pages_data = batch_data.get("pages", [])
            for page_data in pages_data:
                page_number = page_data.get("page_number", 0)
                content = page_data.get("content", "")
                chapter_title = page_data.get("chapter_title")
                section_title = page_data.get("section_title")

                # Use provided content or fall back to page_contents
                if not content and page_number in page_contents:
                    content = page_contents[page_number]

                all_pages.append(ParsedPage(
                    page_number=page_number,
                    content=content,
                    chapter_title=chapter_title,
                    section_title=section_title,
                ))

        # Sort pages by page number
        all_pages.sort(key=lambda p: p.page_number)

        if not all_pages:
            errors.append("No pages found in batch results")
            return ParseResult(errors=errors)

        # Build document structure from page annotations
        document = self._build_from_pages(all_pages)

        return ParseResult(
            document=document,
            pages_parsed=len(all_pages),
            chapters_found=document.chapter_count,
            sections_found=document.section_count,
            errors=errors,
        )

    def _build_from_pages(self, pages: List[ParsedPage]) -> DocumentModel:
        """Build document structure from annotated pages.

        Args:
            pages: List of ParsedPage objects sorted by page number.

        Returns:
            DocumentModel with inferred structure.
        """
        chapters: List[ChapterModel] = []
        current_chapter: Optional[ChapterModel] = None
        current_section: Optional[SectionModel] = None

        for page in pages:
            # Check for new chapter
            if page.chapter_title:
                # Save current chapter
                if current_chapter:
                    if current_section:
                        current_chapter.sections.append(current_section)
                    chapters.append(current_chapter)

                # Start new chapter
                chapter_id = uuid4()
                current_chapter = ChapterModel(
                    id=chapter_id,
                    document_id=self._document_id,
                    title=page.chapter_title,
                    order_index=len(chapters),
                    sections=[],
                )
                current_section = None

            # Check for new section
            if page.section_title:
                # Save current section
                if current_section and current_chapter:
                    current_chapter.sections.append(current_section)

                # Start new section
                section_id = uuid4()
                chapter_id = current_chapter.id if current_chapter else uuid4()
                current_section = SectionModel(
                    id=section_id,
                    chapter_id=chapter_id,
                    title=page.section_title,
                    order_index=len(current_chapter.sections) if current_chapter else 0,
                    pages=[],
                )

            # Ensure we have a chapter and section
            if not current_chapter:
                chapter_id = uuid4()
                current_chapter = ChapterModel(
                    id=chapter_id,
                    document_id=self._document_id,
                    title="Main Content",
                    order_index=0,
                    sections=[],
                )

            if not current_section:
                section_id = uuid4()
                current_section = SectionModel(
                    id=section_id,
                    chapter_id=current_chapter.id,
                    title="Content",
                    order_index=len(current_chapter.sections),
                    pages=[],
                )

            # Add page to current section
            page_model = PageModel(
                id=uuid4(),
                section_id=current_section.id,
                page_number=page.page_number,
                content=page.content,
            )
            page_model.update_word_count()
            current_section.pages.append(page_model)

        # Finalize last chapter and section
        if current_section and current_chapter:
            current_chapter.sections.append(current_section)
        if current_chapter:
            chapters.append(current_chapter)

        # Create document
        return DocumentModel(
            id=self._document_id,
            title="Document",
            chapters=chapters,
        )

    def parse_merged_response(
        self,
        json_data: Dict[str, Any],
        page_contents: Dict[int, str],
    ) -> ParseResult:
        """Parse a merged document structure response.

        Handles the format from MERGE_PROMPT.

        Args:
            json_data: JSON response from merge prompt.
            page_contents: Mapping of page numbers to content.

        Returns:
            ParseResult with document model.
        """
        # Use the same parsing as full response
        return self.parse_full_response(json_data, page_contents)


def parse_vision_response(
    json_data: Dict[str, Any],
    document_id: Optional[UUID] = None,
    page_contents: Optional[Dict[int, str]] = None,
) -> ParseResult:
    """Convenience function to parse vision model response.

    Args:
        json_data: JSON response from vision model.
        document_id: Optional document UUID.
        page_contents: Optional page content mapping.

    Returns:
        ParseResult with parsed document.
    """
    parser = StructureParser(document_id=document_id)
    return parser.parse_full_response(json_data, page_contents)


def merge_batch_results(
    batch_results: List[Dict[str, Any]],
    page_contents: Dict[int, str],
    document_id: Optional[UUID] = None,
) -> ParseResult:
    """Merge multiple batch results into a document.

    Args:
        batch_results: List of JSON responses from batched calls.
        page_contents: Mapping of page numbers to content.
        document_id: Optional document UUID.

    Returns:
        ParseResult with merged document.
    """
    parser = StructureParser(document_id=document_id)
    return parser.parse_batch_responses(batch_results, page_contents)
