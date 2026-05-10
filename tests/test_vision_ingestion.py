"""Tests for vision-based ingestion service."""

import io
import os
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from PIL import Image

from officeplane.ingestion.config import IngestionConfig


# Test fixtures path
FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_PDF_PATH = FIXTURES_DIR / "test_document.pdf"
TEST_IMAGE_PATH = FIXTURES_DIR / "test_image_compress.png"
from officeplane.ingestion.format_detector import (
    DocumentFormat,
    detect_format,
    is_office_document,
    is_pdf,
    needs_conversion,
)
from officeplane.ingestion.ingestion_service import (
    IngestionResult,
    VisionIngestionService,
)
from officeplane.ingestion.vision_adapters.mock import (
    MockVisionAdapter,
    create_mock_response,
)
from officeplane.ingestion.vision_protocol import VisionResponse


# =============================================================================
# Test Fixtures
# =============================================================================


def create_minimal_pdf() -> bytes:
    """Create a minimal valid PDF for testing."""
    # Minimal PDF structure
    return b"""%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >> endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer << /Size 4 /Root 1 0 R >>
startxref
196
%%EOF"""


def create_test_docx_bytes() -> bytes:
    """Create bytes that look like a DOCX file (ZIP with word/ directory)."""
    import zipfile
    from io import BytesIO

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        # Minimal DOCX structure
        zf.writestr("[Content_Types].xml", """<?xml version="1.0"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
</Types>""")
        zf.writestr("word/document.xml", "<document>Test</document>")
    return buffer.getvalue()


# =============================================================================
# Format Detector Tests
# =============================================================================


class TestFormatDetector:
    """Tests for format detection module."""

    def test_detect_pdf(self):
        """Test detecting PDF format."""
        pdf_bytes = create_minimal_pdf()
        fmt = detect_format(pdf_bytes)
        assert fmt == DocumentFormat.PDF

    def test_detect_docx(self):
        """Test detecting DOCX format."""
        docx_bytes = create_test_docx_bytes()
        fmt = detect_format(docx_bytes, "test.docx")
        assert fmt == DocumentFormat.DOCX

    def test_detect_unknown(self):
        """Test detecting unknown format."""
        random_bytes = b"random content that is not a document"
        fmt = detect_format(random_bytes)
        assert fmt == DocumentFormat.UNKNOWN

    def test_detect_short_data(self):
        """Test detecting format with insufficient data."""
        short_bytes = b"PDF"
        fmt = detect_format(short_bytes)
        assert fmt == DocumentFormat.UNKNOWN

    def test_is_pdf(self):
        """Test is_pdf helper function."""
        pdf_bytes = create_minimal_pdf()
        assert is_pdf(pdf_bytes) is True
        assert is_pdf(b"not a pdf") is False

    def test_is_office_document(self):
        """Test is_office_document helper."""
        docx_bytes = create_test_docx_bytes()
        assert is_office_document(docx_bytes, "test.docx") is True
        assert is_office_document(b"not office", "test.txt") is False

    def test_needs_conversion(self):
        """Test needs_conversion helper."""
        pdf_bytes = create_minimal_pdf()
        docx_bytes = create_test_docx_bytes()

        assert needs_conversion(pdf_bytes) is False
        assert needs_conversion(docx_bytes, "test.docx") is True


# =============================================================================
# Mock Vision Adapter Tests
# =============================================================================


class TestMockVisionAdapter:
    """Tests for MockVisionAdapter."""

    @pytest.mark.asyncio
    async def test_analyze_images_default(self):
        """Test default mock response generation."""
        adapter = MockVisionAdapter()

        response = await adapter.analyze_images(
            images=[b"fake_image_1", b"fake_image_2"],
            prompt="Analyze these pages",
        )

        assert response.success
        assert response.json_data is not None
        assert "chapters" in response.json_data
        assert adapter.call_count == 1

    @pytest.mark.asyncio
    async def test_analyze_images_custom_generator(self):
        """Test custom response generator."""
        def custom_generator(images, prompt):
            return {"custom": True, "image_count": len(images)}

        adapter = MockVisionAdapter(response_generator=custom_generator)

        response = await adapter.analyze_images(
            images=[b"img1", b"img2", b"img3"],
            prompt="test",
        )

        assert response.success
        assert response.json_data["custom"] is True
        assert response.json_data["image_count"] == 3

    @pytest.mark.asyncio
    async def test_call_history(self):
        """Test call history tracking."""
        adapter = MockVisionAdapter()

        await adapter.analyze_images([b"img1"], "prompt1")
        await adapter.analyze_images([b"img2", b"img3"], "prompt2")

        assert adapter.call_count == 2
        assert len(adapter.call_history) == 2
        assert adapter.call_history[0]["images_count"] == 1
        assert adapter.call_history[1]["images_count"] == 2

    def test_adapter_properties(self):
        """Test adapter property values."""
        adapter = MockVisionAdapter()

        assert adapter.supports_batch is True
        assert adapter.max_images_per_call == 32
        assert adapter.model_name == "mock"

    @pytest.mark.asyncio
    async def test_reset(self):
        """Test reset functionality."""
        adapter = MockVisionAdapter()
        await adapter.analyze_images([b"img"], "test")

        assert adapter.call_count == 1

        adapter.reset()

        assert adapter.call_count == 0
        assert len(adapter.call_history) == 0


class TestCreateMockResponse:
    """Tests for create_mock_response helper."""

    def test_default_response(self):
        """Test default mock response structure."""
        response = create_mock_response()

        assert response["title"] == "Test Document"
        assert response["author"] == "Test Author"
        assert len(response["chapters"]) == 2
        assert response["chapters"][0]["title"] == "Introduction"

    def test_custom_title(self):
        """Test custom title in mock response."""
        response = create_mock_response(title="Custom Title")

        assert response["title"] == "Custom Title"

    def test_custom_chapters(self):
        """Test custom chapters in mock response."""
        custom_chapters = [
            {"title": "Custom Ch", "sections": [{"title": "S", "pages": [1]}]}
        ]
        response = create_mock_response(chapters=custom_chapters)

        assert len(response["chapters"]) == 1
        assert response["chapters"][0]["title"] == "Custom Ch"


# =============================================================================
# Ingestion Config Tests
# =============================================================================


class TestIngestionConfig:
    """Tests for IngestionConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        config = IngestionConfig()

        assert config.vision_provider == "gemini"
        assert config.vision_model == "gemini-3-flash-preview"
        assert config.image_size_kb == 75
        assert config.pdf_dpi == 150
        assert config.batch_size == 8
        assert config.auto_index is True

    def test_validate_valid_config(self):
        """Test validation passes for valid config (vision mode)."""
        config = IngestionConfig(
            mode="vision",
            vision_provider="mock",
            image_size_kb=100,
            pdf_dpi=150,
            batch_size=16,
        )
        # Should not raise
        config.validate()

    def test_validate_invalid_provider(self):
        """Test validation fails for invalid provider in vision mode."""
        config = IngestionConfig(mode="vision")
        config.vision_provider = "invalid"

        with pytest.raises(ValueError, match="Invalid vision_provider"):
            config.validate()

    def test_validate_missing_api_key(self):
        """Test validation fails when Gemini API key missing in vision mode."""
        config = IngestionConfig(mode="vision", vision_provider="gemini", google_api_key="")

        with pytest.raises(ValueError, match="GOOGLE_API_KEY is required"):
            config.validate()

    def test_validate_invalid_image_size(self):
        """Test validation fails for invalid image size."""
        config = IngestionConfig(mode="vision", vision_provider="mock", image_size_kb=5)

        with pytest.raises(ValueError, match="image_size_kb must be between"):
            config.validate()

    def test_validate_invalid_dpi(self):
        """Test validation fails for invalid DPI."""
        config = IngestionConfig(mode="vision", vision_provider="mock", pdf_dpi=50)

        with pytest.raises(ValueError, match="pdf_dpi must be between"):
            config.validate()


# =============================================================================
# Vision Ingestion Service Tests
# =============================================================================


class TestVisionIngestionService:
    """Tests for VisionIngestionService."""

    @pytest.mark.asyncio
    async def test_init_with_mock_adapter(self):
        """Test service initialization with mock adapter."""
        adapter = MockVisionAdapter()
        config = IngestionConfig(mode="vision", vision_provider="mock")

        service = VisionIngestionService(
            vision_adapter=adapter,
            config=config,
        )

        await service.connect()

        assert service._connected is True
        assert service._vision_adapter is adapter

        await service.close()

    @pytest.mark.asyncio
    async def test_ingest_unknown_format(self):
        """Test ingestion fails for unknown format."""
        adapter = MockVisionAdapter()
        config = IngestionConfig(mode="vision", vision_provider="mock")

        service = VisionIngestionService(
            vision_adapter=adapter,
            config=config,
        )

        result = await service.ingest(
            data=b"not a document",
            filename="unknown.xyz",
        )

        assert result.success is False
        assert "Unknown document format" in result.error

    @pytest.mark.asyncio
    async def test_ingest_needs_driver_for_docx(self):
        """Test ingestion of DOCX requires driver (vision mode)."""
        adapter = MockVisionAdapter()
        config = IngestionConfig(mode="vision", vision_provider="mock")

        service = VisionIngestionService(
            driver=None,  # No driver
            vision_adapter=adapter,
            config=config,
        )

        docx_bytes = create_test_docx_bytes()

        result = await service.ingest(
            data=docx_bytes,
            filename="test.docx",
        )

        assert result.success is False
        assert "Failed to convert" in result.error

    @pytest.mark.asyncio
    async def test_ingestion_result_structure(self):
        """Test IngestionResult has expected fields."""
        result = IngestionResult(
            success=True,
            document_id=uuid4(),
            chapter_count=3,
            section_count=5,
            page_count=10,
        )

        assert result.success is True
        assert result.chapter_count == 3
        assert result.section_count == 5
        assert result.page_count == 10
        assert result.error is None

    @pytest.mark.asyncio
    async def test_progress_callback_called(self):
        """Test progress callback is invoked."""
        # This test verifies the callback mechanism works
        # without actually processing a real document
        progress_stages = []

        def track_progress(stage, current, total):
            progress_stages.append((stage, current, total))

        adapter = MockVisionAdapter()
        config = IngestionConfig(mode="vision", vision_provider="mock")

        service = VisionIngestionService(
            vision_adapter=adapter,
            config=config,
        )

        # Call private method to test callback
        service._report_progress(track_progress, "test_stage", 5, 10)

        assert len(progress_stages) == 1
        assert progress_stages[0] == ("test_stage", 5, 10)


# =============================================================================
# Vision Protocol Tests
# =============================================================================


class TestVisionResponse:
    """Tests for VisionResponse dataclass."""

    def test_success_with_text(self):
        """Test success property with raw text."""
        response = VisionResponse(raw_text="Some text")
        assert response.success is True

    def test_success_with_json(self):
        """Test success property with JSON data."""
        response = VisionResponse(json_data={"key": "value"})
        assert response.success is True

    def test_failure_with_error(self):
        """Test failure property with error."""
        response = VisionResponse(error="Something went wrong")
        assert response.success is False

    def test_failure_empty_response(self):
        """Test failure for empty response."""
        response = VisionResponse()
        assert response.success is False

    def test_response_attributes(self):
        """Test all response attributes."""
        response = VisionResponse(
            raw_text="text",
            json_data={"data": True},
            model="test-model",
            usage={"tokens": 100},
            error=None,
        )

        assert response.raw_text == "text"
        assert response.json_data == {"data": True}
        assert response.model == "test-model"
        assert response.usage == {"tokens": 100}
        assert response.error is None


# =============================================================================
# Integration-like Tests (with mocks)
# =============================================================================


class TestIngestionPipeline:
    """Integration-style tests for the full pipeline with mocks."""

    @pytest.mark.asyncio
    async def test_pipeline_with_mock_pdf(self):
        """Test full pipeline with mocked PDF processing."""
        # Create mock vision adapter with structured response
        def response_generator(images, prompt):
            return {
                "title": "Test PDF",
                "author": "Test Author",
                "chapters": [
                    {
                        "title": "Chapter 1",
                        "summary": "Summary",
                        "sections": [
                            {
                                "title": "Section 1",
                                "pages": [
                                    {"page_number": i + 1, "content": f"Page {i + 1}"}
                                    for i in range(len(images))
                                ],
                            }
                        ],
                    }
                ],
            }

        adapter = MockVisionAdapter(response_generator=response_generator)
        config = IngestionConfig(mode="vision", vision_provider="mock", pdf_dpi=72)

        service = VisionIngestionService(
            vision_adapter=adapter,
            config=config,
        )

        # Create a simple PDF-like bytes (mock pdf_to_images)
        with patch("officeplane.ingestion.ingestion_service.pdf_to_images") as mock_pdf:
            # Return mock page images
            from officeplane.core.render import PageImage

            mock_pdf.return_value = [
                PageImage(
                    page=1,
                    dpi=72,
                    width=100,
                    height=100,
                    sha256="abc",
                    data=create_test_png(),
                )
            ]

            result = await service.ingest(
                data=create_minimal_pdf(),
                filename="test.pdf",
            )

        assert result.success is True
        assert result.chapter_count == 1
        assert result.page_count == 1
        assert result.document is not None
        assert result.document.title == "Test PDF"


def create_test_png() -> bytes:
    """Create a minimal PNG for testing."""
    img = Image.new("RGB", (100, 100), "white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


# =============================================================================
# Tests with Real Fixtures
# =============================================================================


class TestRealPDFFixture:
    """Tests using the real PDF fixture."""

    @pytest.fixture
    def real_pdf_bytes(self) -> bytes:
        """Load the real test PDF."""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test fixture not found: {TEST_PDF_PATH}")
        return TEST_PDF_PATH.read_bytes()

    def test_detect_real_pdf(self, real_pdf_bytes):
        """Test format detection on real PDF."""
        fmt = detect_format(real_pdf_bytes)
        assert fmt == DocumentFormat.PDF

    def test_is_pdf_real(self, real_pdf_bytes):
        """Test is_pdf on real PDF."""
        assert is_pdf(real_pdf_bytes) is True

    @pytest.mark.asyncio
    async def test_ingest_real_pdf_with_mock_vision(self, real_pdf_bytes):
        """Test ingestion of real PDF with mock vision adapter."""
        def response_generator(images, prompt):
            return {
                "title": "Regulatory Intelligence Platform",
                "author": "OSPYN",
                "chapters": [
                    {
                        "title": "Product Overview",
                        "summary": "Overview of the platform",
                        "sections": [
                            {
                                "title": "Introduction",
                                "pages": [
                                    {"page_number": i + 1, "content": f"Content for page {i + 1}"}
                                    for i in range(len(images))
                                ],
                            }
                        ],
                    }
                ],
            }

        adapter = MockVisionAdapter(response_generator=response_generator)
        config = IngestionConfig(mode="vision", vision_provider="mock", pdf_dpi=100, batch_size=16)

        service = VisionIngestionService(
            vision_adapter=adapter,
            config=config,
        )

        result = await service.ingest(
            data=real_pdf_bytes,
            filename="test_document.pdf",
        )

        assert result.success is True
        assert result.chapter_count >= 1
        assert result.page_count >= 1
        assert result.document is not None
        print(f"Ingested: {result.document.title}")
        print(f"Chapters: {result.chapter_count}, Pages: {result.page_count}")


class TestGeminiIntegration:
    """Integration tests with real Gemini API (requires API key)."""

    @pytest.fixture
    def gemini_api_key(self) -> str:
        """Get Gemini API key from environment."""
        key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        if not key:
            pytest.skip("GEMINI_API_KEY or GOOGLE_API_KEY not set")
        return key

    @pytest.fixture
    def real_pdf_bytes(self) -> bytes:
        """Load the real test PDF."""
        if not TEST_PDF_PATH.exists():
            pytest.skip(f"Test fixture not found: {TEST_PDF_PATH}")
        return TEST_PDF_PATH.read_bytes()

    @pytest.mark.asyncio
    async def test_gemini_vision_adapter(self, gemini_api_key):
        """Test GeminiVisionAdapter with a simple image."""
        from officeplane.ingestion.vision_adapters.gemini import GeminiVisionAdapter

        adapter = GeminiVisionAdapter(
            api_key=gemini_api_key,
            model="gemini-3-flash-preview",
        )

        # Create a simple test image
        test_image = create_test_png()

        response = await adapter.analyze_images(
            images=[test_image],
            prompt="Describe this image in one sentence.",
        )

        assert response.success, f"Gemini API failed: {response.error}"
        assert response.raw_text or response.json_data
        print(f"Gemini response: {response.raw_text[:200] if response.raw_text else response.json_data}")

    @pytest.mark.asyncio
    async def test_full_ingestion_with_gemini(self, gemini_api_key, real_pdf_bytes):
        """Test full ingestion pipeline with real Gemini API."""
        from officeplane.ingestion.vision_adapters.gemini import GeminiVisionAdapter

        adapter = GeminiVisionAdapter(
            api_key=gemini_api_key,
            model="gemini-3-flash-preview",
        )

        config = IngestionConfig(
            mode="vision",
            vision_provider="gemini",
            vision_model="gemini-3-flash-preview",
            pdf_dpi=100,
            batch_size=8,
            image_size_kb=75,
        )

        service = VisionIngestionService(
            vision_adapter=adapter,
            config=config,
        )

        progress_log = []

        def progress_callback(stage, current, total):
            progress_log.append((stage, current, total))
            print(f"Progress: {stage} - {current}/{total}")

        result = await service.ingest(
            data=real_pdf_bytes,
            filename="Regulatory_Intelligence_Platform.pdf",
            progress_callback=progress_callback,
        )

        print(f"\n=== Ingestion Result ===")
        print(f"Success: {result.success}")
        if result.error:
            print(f"Error: {result.error}")
        if result.document:
            print(f"Title: {result.document.title}")
            print(f"Author: {result.document.author}")
            print(f"Chapters: {result.chapter_count}")
            print(f"Sections: {result.section_count}")
            print(f"Pages: {result.page_count}")

        assert result.success, f"Ingestion failed: {result.error}"
        assert result.chapter_count >= 1
        assert result.page_count >= 1
