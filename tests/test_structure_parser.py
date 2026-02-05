"""Tests for structure parser module."""

from uuid import UUID, uuid4

import pytest

from officeplane.ingestion.structure_parser import (
    ParseResult,
    ParsedPage,
    StructureParser,
    merge_batch_results,
    parse_vision_response,
)


class TestStructureParser:
    """Tests for StructureParser class."""

    def test_parse_full_response_basic(self):
        """Test parsing a basic complete response."""
        json_data = {
            "title": "Test Document",
            "author": "Test Author",
            "chapters": [
                {
                    "title": "Chapter 1",
                    "summary": "First chapter summary",
                    "sections": [
                        {
                            "title": "Section 1.1",
                            "pages": [
                                {"page_number": 1, "content": "Page 1 content"},
                                {"page_number": 2, "content": "Page 2 content"},
                            ],
                        }
                    ],
                }
            ],
        }

        parser = StructureParser()
        result = parser.parse_full_response(json_data)

        assert result.success
        assert result.document is not None
        assert result.document.title == "Test Document"
        assert result.document.author == "Test Author"
        assert result.chapters_found == 1
        assert result.sections_found == 1
        assert result.pages_parsed == 2

    def test_parse_full_response_multiple_chapters(self):
        """Test parsing multiple chapters."""
        json_data = {
            "title": "Multi-Chapter Book",
            "author": None,
            "chapters": [
                {
                    "title": "Introduction",
                    "summary": "Intro summary",
                    "sections": [
                        {"title": "Overview", "pages": [1, 2]},
                    ],
                },
                {
                    "title": "Main Content",
                    "summary": "Main summary",
                    "sections": [
                        {"title": "Details", "pages": [3, 4, 5]},
                        {"title": "Examples", "pages": [6, 7]},
                    ],
                },
            ],
        }

        page_contents = {
            1: "Page 1 text",
            2: "Page 2 text",
            3: "Page 3 text",
            4: "Page 4 text",
            5: "Page 5 text",
            6: "Page 6 text",
            7: "Page 7 text",
        }

        parser = StructureParser()
        result = parser.parse_full_response(json_data, page_contents)

        assert result.success
        assert result.chapters_found == 2
        assert result.sections_found == 3
        assert result.pages_parsed == 7

        # Verify chapter structure
        doc = result.document
        assert doc.chapters[0].title == "Introduction"
        assert doc.chapters[1].title == "Main Content"
        assert len(doc.chapters[1].sections) == 2

    def test_parse_full_response_with_page_numbers_only(self):
        """Test parsing when pages are just numbers."""
        json_data = {
            "title": "Simple Doc",
            "chapters": [
                {
                    "title": "Only Chapter",
                    "sections": [
                        {"title": "Only Section", "pages": [1, 2, 3]},
                    ],
                }
            ],
        }

        page_contents = {
            1: "Content for page 1",
            2: "Content for page 2",
            3: "Content for page 3",
        }

        parser = StructureParser()
        result = parser.parse_full_response(json_data, page_contents)

        assert result.success
        doc = result.document
        pages = doc.chapters[0].sections[0].pages
        assert len(pages) == 3
        assert pages[0].content == "Content for page 1"
        assert pages[1].page_number == 2

    def test_parse_full_response_no_chapters(self):
        """Test parsing fails when no chapters present."""
        json_data = {
            "title": "Empty Document",
            "chapters": [],
        }

        parser = StructureParser()
        result = parser.parse_full_response(json_data)

        assert not result.success
        assert "No chapters found" in result.errors[0]

    def test_parse_full_response_missing_sections(self):
        """Test parsing creates default section when none present."""
        json_data = {
            "title": "No Sections",
            "chapters": [
                {
                    "title": "Chapter Without Sections",
                    "pages": [{"page_number": 1, "content": "Content"}],
                }
            ],
        }

        parser = StructureParser()
        result = parser.parse_full_response(json_data)

        assert result.success
        assert result.sections_found == 1
        assert result.document.chapters[0].sections[0].title == "Main Content"

    def test_parse_with_custom_document_id(self):
        """Test parsing with a custom document ID."""
        custom_id = uuid4()
        json_data = {
            "title": "Custom ID Doc",
            "chapters": [
                {
                    "title": "Chapter",
                    "sections": [{"title": "Section", "pages": [1]}],
                }
            ],
        }

        parser = StructureParser(document_id=custom_id)
        result = parser.parse_full_response(json_data)

        assert result.success
        assert result.document.id == custom_id

    def test_parse_batch_responses_basic(self):
        """Test parsing batch responses."""
        batch_results = [
            {
                "pages": [
                    {"page_number": 1, "chapter_title": "Chapter 1", "content": "P1"},
                    {"page_number": 2, "section_title": "Section 1.1", "content": "P2"},
                ]
            },
            {
                "pages": [
                    {"page_number": 3, "chapter_title": "Chapter 2", "content": "P3"},
                    {"page_number": 4, "content": "P4"},
                ]
            },
        ]

        page_contents = {1: "P1", 2: "P2", 3: "P3", 4: "P4"}

        parser = StructureParser()
        result = parser.parse_batch_responses(batch_results, page_contents)

        assert result.success
        assert result.pages_parsed == 4
        assert result.chapters_found == 2

    def test_parse_batch_responses_empty(self):
        """Test parsing empty batch results."""
        parser = StructureParser()
        result = parser.parse_batch_responses([], {})

        assert not result.success
        assert "No pages found" in result.errors[0]

    def test_word_count_updated(self):
        """Test that word count is updated for pages."""
        json_data = {
            "title": "Word Count Test",
            "chapters": [
                {
                    "title": "Chapter",
                    "sections": [
                        {
                            "title": "Section",
                            "pages": [
                                {"page_number": 1, "content": "one two three four five"}
                            ],
                        }
                    ],
                }
            ],
        }

        parser = StructureParser()
        result = parser.parse_full_response(json_data)

        page = result.document.chapters[0].sections[0].pages[0]
        assert page.word_count == 5


class TestParsedPage:
    """Tests for ParsedPage dataclass."""

    def test_parsed_page_creation(self):
        """Test creating a ParsedPage."""
        page = ParsedPage(
            page_number=1,
            content="Test content",
            chapter_title="Chapter 1",
            section_title="Section 1",
        )

        assert page.page_number == 1
        assert page.content == "Test content"
        assert page.chapter_title == "Chapter 1"
        assert page.section_title == "Section 1"

    def test_parsed_page_defaults(self):
        """Test ParsedPage default values."""
        page = ParsedPage(page_number=1, content="Content")

        assert page.chapter_title is None
        assert page.section_title is None


class TestParseResult:
    """Tests for ParseResult dataclass."""

    def test_parse_result_success(self):
        """Test ParseResult success property."""
        from officeplane.documents.models import DocumentModel

        doc = DocumentModel(title="Test")
        result = ParseResult(document=doc, pages_parsed=5)

        assert result.success is True

    def test_parse_result_failure_no_document(self):
        """Test ParseResult failure when no document."""
        result = ParseResult()

        assert result.success is False

    def test_parse_result_failure_with_errors(self):
        """Test ParseResult failure with errors."""
        from officeplane.documents.models import DocumentModel

        doc = DocumentModel(title="Test")
        result = ParseResult(document=doc, errors=["Some error"])

        assert result.success is False


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_parse_vision_response(self):
        """Test parse_vision_response function."""
        json_data = {
            "title": "Test",
            "chapters": [
                {"title": "Ch1", "sections": [{"title": "S1", "pages": [1]}]}
            ],
        }

        result = parse_vision_response(json_data)

        assert result.success
        assert result.document.title == "Test"

    def test_parse_vision_response_with_document_id(self):
        """Test parse_vision_response with custom document ID."""
        custom_id = uuid4()
        json_data = {
            "title": "Test",
            "chapters": [
                {"title": "Ch1", "sections": [{"title": "S1", "pages": [1]}]}
            ],
        }

        result = parse_vision_response(json_data, document_id=custom_id)

        assert result.document.id == custom_id

    def test_merge_batch_results(self):
        """Test merge_batch_results function."""
        batch_results = [
            {
                "pages": [
                    {"page_number": 1, "chapter_title": "Ch1", "content": "Content 1"},
                ]
            },
            {
                "pages": [
                    {"page_number": 2, "content": "Content 2"},
                ]
            },
        ]
        page_contents = {1: "Content 1", 2: "Content 2"}

        result = merge_batch_results(batch_results, page_contents)

        assert result.success
        assert result.pages_parsed == 2
