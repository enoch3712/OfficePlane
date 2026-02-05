"""
High-level document operations for agents.

These classes provide semantic operations that agents can easily understand
and use, built on top of the DocumentEditor foundation.

Architecture:
    StructureReader  - Understand document structure (TOC, chapters, sections)
    ContentModifier  - Insert, delete, replace content at semantic locations
    TableBuilder     - Create and manipulate tables with templates

Example:
    with DocumentEditor("report.docx") as editor:
        # Read structure
        structure = StructureReader(editor)
        toc = structure.get_table_of_contents()
        chapters = structure.find_chapters()

        # Modify content
        content = ContentModifier(editor)
        content.insert_after_heading("Introduction", "New paragraph text")
        content.replace_in_section("Chapter 1", "old", "new")

        # Build tables
        tables = TableBuilder(editor)
        tables.create_data_table([
            ["Name", "Age", "City"],
            ["Alice", "30", "NYC"],
            ["Bob", "25", "LA"],
        ])
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple, Union

from officeplane.doctools.result import (
    DocError,
    ErrorCode,
    Err,
    Ok,
    Result,
    collect_results,
)
from officeplane.doctools.editor import (
    DocumentEditor,
    HeadingRef,
    ParagraphRef,
    TableRef,
)


# =============================================================================
# Data Classes for Operations
# =============================================================================


@dataclass
class TOCEntry:
    """Table of contents entry."""

    level: int
    text: str
    paragraph_index: int
    children: List[TOCEntry] = field(default_factory=list)


@dataclass
class DocumentSection:
    """A logical section of the document (heading + content until next heading)."""

    heading: HeadingRef
    content_start: int  # First paragraph index after heading
    content_end: int  # Last paragraph index (exclusive) - next heading or end
    paragraphs: List[ParagraphRef] = field(default_factory=list)


@dataclass
class InsertLocation:
    """Specifies where to insert content."""

    class Position(Enum):
        BEFORE = auto()
        AFTER = auto()
        REPLACE = auto()

    position: Position
    anchor_type: str  # "heading", "paragraph", "table", "text"
    anchor_value: Union[str, int]  # heading text, paragraph index, or search text


# =============================================================================
# StructureReader - Understand document structure
# =============================================================================


class StructureReader:
    """
    Read and understand document structure.

    Provides semantic access to document organization:
    - Table of contents
    - Chapters and sections
    - Heading hierarchy
    - Section boundaries
    """

    def __init__(self, editor: DocumentEditor):
        """
        Initialize with an open DocumentEditor.

        Args:
            editor: An open DocumentEditor instance
        """
        self.editor = editor

    def get_table_of_contents(self, max_level: int = 3) -> Result[List[TOCEntry]]:
        """
        Build a table of contents from document headings.

        Args:
            max_level: Maximum heading level to include (1-9)

        Returns:
            Result containing list of TOCEntry objects (tree structure)
        """
        headings_result = self.editor.find_headings()
        if headings_result.is_err():
            return Err(headings_result.unwrap_err())

        headings = headings_result.unwrap()

        # Filter by max level
        headings = [h for h in headings if h.level <= max_level]

        if not headings:
            return Ok([])

        # Build tree structure
        root_entries: List[TOCEntry] = []
        stack: List[TOCEntry] = []

        for heading in headings:
            entry = TOCEntry(
                level=heading.level,
                text=heading.text,
                paragraph_index=heading.index,
            )

            # Find parent (most recent entry with lower level)
            while stack and stack[-1].level >= heading.level:
                stack.pop()

            if stack:
                stack[-1].children.append(entry)
            else:
                root_entries.append(entry)

            stack.append(entry)

        return Ok(root_entries)

    def get_flat_toc(self, max_level: int = 3) -> Result[List[Dict[str, Any]]]:
        """
        Get a flat list of TOC entries (easier for agents to process).

        Returns:
            Result containing list of dicts with level, text, index, indent
        """
        headings_result = self.editor.find_headings()
        if headings_result.is_err():
            return Err(headings_result.unwrap_err())

        headings = headings_result.unwrap()
        entries = [
            {
                "level": h.level,
                "text": h.text,
                "index": h.index,
                "indent": "  " * (h.level - 1),
            }
            for h in headings
            if h.level <= max_level
        ]

        return Ok(entries)

    def find_sections(self) -> Result[List[DocumentSection]]:
        """
        Find all sections (heading + content) in the document.

        Returns:
            Result containing list of DocumentSection objects
        """
        headings_result = self.editor.find_headings()
        if headings_result.is_err():
            return Err(headings_result.unwrap_err())

        headings = headings_result.unwrap()
        if not headings:
            return Ok([])

        stats_result = self.editor.get_stats()
        if stats_result.is_err():
            return Err(stats_result.unwrap_err())

        total_paragraphs = stats_result.unwrap()["paragraph_count"]

        sections: List[DocumentSection] = []

        for i, heading in enumerate(headings):
            content_start = heading.index + 1

            # Content ends at next heading or document end
            if i + 1 < len(headings):
                content_end = headings[i + 1].index
            else:
                content_end = total_paragraphs

            # Get paragraph refs for the section
            paragraphs: List[ParagraphRef] = []
            for idx in range(content_start, content_end):
                para_result = self.editor.get_paragraph(idx)
                if para_result.is_ok():
                    paragraphs.append(para_result.unwrap())

            sections.append(
                DocumentSection(
                    heading=heading,
                    content_start=content_start,
                    content_end=content_end,
                    paragraphs=paragraphs,
                )
            )

        return Ok(sections)

    def find_section_by_heading(
        self,
        heading_text: str,
        exact_match: bool = False,
    ) -> Result[Optional[DocumentSection]]:
        """
        Find a section by its heading text.

        Args:
            heading_text: Text to search for in headings
            exact_match: If True, require exact match; otherwise substring match

        Returns:
            Result containing DocumentSection or None if not found
        """
        sections_result = self.find_sections()
        if sections_result.is_err():
            return Err(sections_result.unwrap_err())

        sections = sections_result.unwrap()

        for section in sections:
            if exact_match:
                if section.heading.text == heading_text:
                    return Ok(section)
            else:
                if heading_text.lower() in section.heading.text.lower():
                    return Ok(section)

        return Ok(None)

    def get_chapter_index(
        self,
        chapter_level: int = 1,
    ) -> Result[List[Dict[str, Any]]]:
        """
        Get a list of chapters (top-level headings).

        Args:
            chapter_level: What heading level counts as a chapter (default 1)

        Returns:
            Result containing list of chapter info dicts
        """
        headings_result = self.editor.find_headings(level=chapter_level)
        if headings_result.is_err():
            return Err(headings_result.unwrap_err())

        chapters = [
            {
                "number": i + 1,
                "title": h.text,
                "index": h.index,
            }
            for i, h in enumerate(headings_result.unwrap())
        ]

        return Ok(chapters)


# =============================================================================
# ContentModifier - Insert, delete, replace content
# =============================================================================


class ContentModifier:
    """
    Modify document content at semantic locations.

    Provides high-level content operations:
    - Insert content after/before headings
    - Replace text in specific sections
    - Delete sections or paragraphs
    - Move content between sections
    """

    def __init__(self, editor: DocumentEditor):
        """
        Initialize with an open DocumentEditor.

        Args:
            editor: An open DocumentEditor instance
        """
        self.editor = editor
        self.structure = StructureReader(editor)

    def insert_after_heading(
        self,
        heading_text: str,
        content: Union[str, List[str]],
        style: Optional[str] = None,
    ) -> Result[List[ParagraphRef]]:
        """
        Insert content after a heading.

        Args:
            heading_text: Text of heading to find (substring match)
            content: Single paragraph or list of paragraphs to insert
            style: Optional style for the paragraphs

        Returns:
            Result containing list of inserted ParagraphRefs
        """
        # Find the heading
        headings_result = self.editor.find_headings(contains=heading_text)
        if headings_result.is_err():
            return Err(headings_result.unwrap_err())

        headings = headings_result.unwrap()
        if not headings:
            return Err(
                DocError.element_not_found("heading", heading_text, "entire document")
            )

        heading = headings[0]  # Use first match

        # Normalize content to list
        if isinstance(content, str):
            content = [content]

        # Insert paragraphs after the heading
        inserted: List[ParagraphRef] = []
        current_anchor = heading.index

        for text in content:
            result = self.editor.insert_paragraph_after(current_anchor, text, style)
            if result.is_err():
                return Err(result.unwrap_err())

            para_ref = result.unwrap()
            inserted.append(para_ref)
            current_anchor = para_ref.index

        return Ok(inserted)

    def insert_before_heading(
        self,
        heading_text: str,
        content: Union[str, List[str]],
        style: Optional[str] = None,
    ) -> Result[List[ParagraphRef]]:
        """
        Insert content before a heading.

        Args:
            heading_text: Text of heading to find
            content: Single paragraph or list of paragraphs to insert
            style: Optional style for the paragraphs

        Returns:
            Result containing list of inserted ParagraphRefs
        """
        # Find the heading
        headings_result = self.editor.find_headings(contains=heading_text)
        if headings_result.is_err():
            return Err(headings_result.unwrap_err())

        headings = headings_result.unwrap()
        if not headings:
            return Err(
                DocError.element_not_found("heading", heading_text, "entire document")
            )

        heading = headings[0]

        # Insert before the heading = insert after paragraph before it
        if heading.index == 0:
            # Heading is at start - add to beginning
            if isinstance(content, str):
                content = [content]

            inserted: List[ParagraphRef] = []
            for i, text in enumerate(content):
                result = self.editor.add_paragraph(text, style)
                if result.is_err():
                    return Err(result.unwrap_err())
                inserted.append(result.unwrap())

            return Ok(inserted)

        # Otherwise insert after the previous paragraph
        anchor_index = heading.index - 1

        if isinstance(content, str):
            content = [content]

        inserted = []
        for text in content:
            result = self.editor.insert_paragraph_after(anchor_index, text, style)
            if result.is_err():
                return Err(result.unwrap_err())

            para_ref = result.unwrap()
            inserted.append(para_ref)
            anchor_index = para_ref.index

        return Ok(inserted)

    def replace_in_section(
        self,
        heading_text: str,
        old_text: str,
        new_text: str,
    ) -> Result[int]:
        """
        Replace text only within a specific section.

        Args:
            heading_text: Heading of section to search in
            old_text: Text to find
            new_text: Replacement text

        Returns:
            Result containing count of replacements
        """
        section_result = self.structure.find_section_by_heading(heading_text)
        if section_result.is_err():
            return Err(section_result.unwrap_err())

        section = section_result.unwrap()
        if section is None:
            return Err(
                DocError.element_not_found("section", heading_text, "document")
            )

        count = 0
        for i in range(section.content_start, section.content_end):
            result = self.editor.replace_text(old_text, new_text, paragraph_index=i)
            if result.is_ok():
                count += result.unwrap()

        return Ok(count)

    def delete_section_content(
        self,
        heading_text: str,
        keep_heading: bool = True,
    ) -> Result[int]:
        """
        Delete all content in a section.

        Args:
            heading_text: Heading of section to clear
            keep_heading: If True, keep the heading; if False, delete it too

        Returns:
            Result containing count of deleted paragraphs
        """
        section_result = self.structure.find_section_by_heading(heading_text)
        if section_result.is_err():
            return Err(section_result.unwrap_err())

        section = section_result.unwrap()
        if section is None:
            return Err(
                DocError.element_not_found("section", heading_text, "document")
            )

        # Delete from end to start to maintain indices
        start = section.heading.index if not keep_heading else section.content_start
        end = section.content_end

        deleted = 0
        for i in range(end - 1, start - 1, -1):
            result = self.editor.delete_paragraph(i)
            if result.is_ok():
                deleted += 1

        return Ok(deleted)

    def append_to_section(
        self,
        heading_text: str,
        content: Union[str, List[str]],
        style: Optional[str] = None,
    ) -> Result[List[ParagraphRef]]:
        """
        Append content to the end of a section (before next heading).

        Args:
            heading_text: Heading of section
            content: Content to append
            style: Optional style

        Returns:
            Result containing list of added ParagraphRefs
        """
        section_result = self.structure.find_section_by_heading(heading_text)
        if section_result.is_err():
            return Err(section_result.unwrap_err())

        section = section_result.unwrap()
        if section is None:
            return Err(
                DocError.element_not_found("section", heading_text, "document")
            )

        # Insert after the last paragraph in the section
        # (which is content_end - 1)
        if section.content_start >= section.content_end:
            # Empty section - insert after heading
            anchor = section.heading.index
        else:
            anchor = section.content_end - 1

        if isinstance(content, str):
            content = [content]

        inserted: List[ParagraphRef] = []
        for text in content:
            result = self.editor.insert_paragraph_after(anchor, text, style)
            if result.is_err():
                return Err(result.unwrap_err())

            para_ref = result.unwrap()
            inserted.append(para_ref)
            anchor = para_ref.index

        return Ok(inserted)


# =============================================================================
# TableBuilder - Create and modify tables
# =============================================================================


class TableBuilder:
    """
    Create and manipulate tables with templates.

    Provides high-level table operations:
    - Create data tables from lists
    - Apply styling templates
    - Insert tables at specific locations
    - Modify existing tables
    """

    def __init__(self, editor: DocumentEditor):
        """
        Initialize with an open DocumentEditor.

        Args:
            editor: An open DocumentEditor instance
        """
        self.editor = editor

    def create_data_table(
        self,
        data: List[List[str]],
        has_header: bool = True,
        style: Optional[str] = "Table Grid",
    ) -> Result[TableRef]:
        """
        Create a table from a 2D list of data.

        Args:
            data: 2D list where first row can be headers
            has_header: If True, first row is treated as header
            style: Table style name

        Returns:
            Result containing TableRef
        """
        if not data:
            return Err(
                DocError(
                    code=ErrorCode.INVALID_ARGUMENT,
                    message="Data cannot be empty",
                )
            )

        rows = len(data)
        cols = max(len(row) for row in data)

        # Create table
        table_result = self.editor.add_table(rows, cols, style)
        if table_result.is_err():
            return Err(table_result.unwrap_err())

        table_ref = table_result.unwrap()

        # Fill data
        fill_result = self.editor.fill_table(table_ref.index, data)
        if fill_result.is_err():
            return Err(fill_result.unwrap_err())

        return Ok(table_ref)

    def create_key_value_table(
        self,
        data: Dict[str, str],
        key_header: str = "Property",
        value_header: str = "Value",
        style: Optional[str] = "Table Grid",
    ) -> Result[TableRef]:
        """
        Create a two-column key-value table from a dictionary.

        Args:
            data: Dictionary of key-value pairs
            key_header: Header for the key column
            value_header: Header for the value column
            style: Table style name

        Returns:
            Result containing TableRef
        """
        table_data = [[key_header, value_header]]
        for key, value in data.items():
            table_data.append([str(key), str(value)])

        return self.create_data_table(table_data, has_header=True, style=style)

    def insert_table_after_heading(
        self,
        heading_text: str,
        data: List[List[str]],
        style: Optional[str] = "Table Grid",
    ) -> Result[TableRef]:
        """
        Insert a table after a specific heading.

        Note: This creates a table at the end of the document.
        Use for new documents or when appending tables.

        Args:
            heading_text: Heading text to find
            data: Table data
            style: Table style

        Returns:
            Result containing TableRef
        """
        # First verify the heading exists
        headings_result = self.editor.find_headings(contains=heading_text)
        if headings_result.is_err():
            return Err(headings_result.unwrap_err())

        headings = headings_result.unwrap()
        if not headings:
            return Err(
                DocError.element_not_found("heading", heading_text, "document")
            )

        # Create the table
        return self.create_data_table(data, has_header=True, style=style)

    def add_row(
        self,
        table_index: int,
        data: List[str],
    ) -> Result[None]:
        """
        Add a row to an existing table.

        Note: python-docx tables have fixed size.
        This creates a new row by modifying the XML.

        Args:
            table_index: Index of the table
            data: Row data

        Returns:
            Result indicating success
        """
        if self.editor.doc is None:
            return Err(DocError(code=ErrorCode.OPERATION_FAILED, message="No document open"))

        tables = self.editor.doc.tables
        if table_index < 0 or table_index >= len(tables):
            return Err(
                DocError.invalid_position(table_index, f"0 to {len(tables) - 1}")
            )

        try:
            table = tables[table_index]
            row = table.add_row()

            for i, cell_value in enumerate(data):
                if i < len(row.cells):
                    row.cells[i].text = str(cell_value)

            self.editor._mark_modified()
            return Ok(None)

        except Exception as e:
            return Err(DocError.from_exception(e, "Adding row"))

    def update_cell(
        self,
        table_index: int,
        row: int,
        col: int,
        value: str,
    ) -> Result[None]:
        """
        Update a single cell in a table.

        Args:
            table_index: Index of the table
            row: Row index
            col: Column index
            value: New cell value

        Returns:
            Result indicating success
        """
        return self.editor.set_cell(table_index, row, col, value)

    def get_table_data(self, table_index: int) -> Result[List[List[str]]]:
        """
        Read all data from a table.

        Args:
            table_index: Index of the table

        Returns:
            Result containing 2D list of cell values
        """
        if self.editor.doc is None:
            return Err(DocError(code=ErrorCode.OPERATION_FAILED, message="No document open"))

        tables = self.editor.doc.tables
        if table_index < 0 or table_index >= len(tables):
            return Err(
                DocError.invalid_position(table_index, f"0 to {len(tables) - 1}")
            )

        try:
            table = tables[table_index]
            data: List[List[str]] = []

            for row in table.rows:
                row_data = [cell.text for cell in row.cells]
                data.append(row_data)

            return Ok(data)

        except Exception as e:
            return Err(DocError.from_exception(e, "Reading table"))
