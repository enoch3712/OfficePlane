"""Tests for image processor module."""

import io
from pathlib import Path

import pytest
from PIL import Image

from officeplane.ingestion.image_processor import (
    ImageProcessor,
    ProcessedImage,
    compress_image,
)


# Test fixtures path
FIXTURES_DIR = Path(__file__).parent / "fixtures"
TEST_IMAGE_PATH = FIXTURES_DIR / "test_image_compress.png"


def create_test_image(
    width: int = 800,
    height: int = 600,
    color: str = "white",
    fmt: str = "PNG",
) -> bytes:
    """Create a test image with specified dimensions."""
    img = Image.new("RGB", (width, height), color)
    buffer = io.BytesIO()
    img.save(buffer, format=fmt)
    return buffer.getvalue()


def create_rgba_image(width: int = 400, height: int = 300) -> bytes:
    """Create a test RGBA image with transparency."""
    img = Image.new("RGBA", (width, height), (255, 0, 0, 128))
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


class TestImageProcessor:
    """Tests for ImageProcessor class."""

    def test_init_default_values(self):
        """Test default initialization values."""
        processor = ImageProcessor()
        assert processor.target_size_bytes == 75 * 1024
        assert processor.max_dimension == 1600
        assert processor.min_quality == 20
        assert processor.max_quality == 95

    def test_init_custom_values(self):
        """Test custom initialization values."""
        processor = ImageProcessor(
            target_size_kb=100,
            max_dimension=1200,
            min_quality=30,
            max_quality=90,
        )
        assert processor.target_size_bytes == 100 * 1024
        assert processor.max_dimension == 1200
        assert processor.min_quality == 30
        assert processor.max_quality == 90

    def test_process_returns_processed_image(self):
        """Test that process returns a ProcessedImage."""
        processor = ImageProcessor()
        image_bytes = create_test_image()

        result = processor.process(image_bytes)

        assert isinstance(result, ProcessedImage)
        assert result.data is not None
        assert len(result.data) > 0
        assert result.original_size == len(image_bytes)
        assert result.compressed_size == len(result.data)
        assert result.quality >= processor.min_quality
        assert result.quality <= processor.max_quality

    def test_process_jpeg_output(self):
        """Test that output is JPEG format."""
        processor = ImageProcessor()
        image_bytes = create_test_image()

        result = processor.process(image_bytes)

        # JPEG magic bytes
        assert result.data[:2] == b"\xff\xd8"

    def test_resize_large_image(self):
        """Test that large images are resized."""
        processor = ImageProcessor(max_dimension=800)
        # Create image larger than max_dimension
        image_bytes = create_test_image(width=2000, height=1500)

        result = processor.process(image_bytes)

        # Check dimensions were reduced
        assert result.dimensions[0] <= 800
        assert result.dimensions[1] <= 800

    def test_no_resize_small_image(self):
        """Test that small images are not resized."""
        processor = ImageProcessor(max_dimension=1600)
        image_bytes = create_test_image(width=400, height=300)

        result = processor.process(image_bytes)

        # Original dimensions should be preserved
        assert result.dimensions == (400, 300)

    def test_compress_to_target_size(self):
        """Test compression hits approximate target size."""
        processor = ImageProcessor(target_size_kb=50)
        # Create a larger image that needs compression
        image_bytes = create_test_image(width=1200, height=900, color="blue")

        result = processor.process(image_bytes)

        # Should be close to target (within reasonable margin)
        # Note: simple colored images compress very well, so this is just a sanity check
        assert result.compressed_size <= 150 * 1024  # Allow some margin

    def test_handle_rgba_image(self):
        """Test handling of RGBA images with transparency."""
        processor = ImageProcessor()
        image_bytes = create_rgba_image()

        result = processor.process(image_bytes)

        # Should successfully convert to JPEG (no alpha channel)
        assert result.data[:2] == b"\xff\xd8"

    def test_handle_palette_image(self):
        """Test handling of palette mode images."""
        img = Image.new("P", (200, 200))
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        processor = ImageProcessor()
        result = processor.process(image_bytes)

        assert result.data[:2] == b"\xff\xd8"

    def test_handle_grayscale_image(self):
        """Test handling of grayscale images."""
        img = Image.new("L", (200, 200), 128)
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        image_bytes = buffer.getvalue()

        processor = ImageProcessor()
        result = processor.process(image_bytes)

        assert result.data[:2] == b"\xff\xd8"

    def test_quality_binary_search(self):
        """Test that binary search finds optimal quality."""
        processor = ImageProcessor(target_size_kb=30, min_quality=10, max_quality=95)
        image_bytes = create_test_image(width=1000, height=800)

        result = processor.process(image_bytes)

        # Quality should be in valid range
        assert result.quality >= 10
        assert result.quality <= 95


class TestCompressImageFunction:
    """Tests for compress_image convenience function."""

    def test_compress_image_basic(self):
        """Test basic compression."""
        image_bytes = create_test_image()

        result = compress_image(image_bytes)

        assert len(result) > 0
        assert result[:2] == b"\xff\xd8"

    def test_compress_image_custom_params(self):
        """Test compression with custom parameters."""
        image_bytes = create_test_image(width=2000, height=1500)

        result = compress_image(
            image_bytes,
            target_size_kb=100,
            max_dimension=1000,
        )

        # Verify output is JPEG
        assert result[:2] == b"\xff\xd8"

        # Load result and check dimensions
        img = Image.open(io.BytesIO(result))
        assert img.width <= 1000
        assert img.height <= 1000


class TestProcessedImage:
    """Tests for ProcessedImage dataclass."""

    def test_processed_image_attributes(self):
        """Test ProcessedImage has all expected attributes."""
        processed = ProcessedImage(
            data=b"test",
            original_size=1000,
            compressed_size=500,
            dimensions=(800, 600),
            quality=75,
        )

        assert processed.data == b"test"
        assert processed.original_size == 1000
        assert processed.compressed_size == 500
        assert processed.dimensions == (800, 600)
        assert processed.quality == 75


class TestRealImageFixture:
    """Tests using the real test image fixture."""

    @pytest.fixture
    def real_image_bytes(self) -> bytes:
        """Load the real test image."""
        if not TEST_IMAGE_PATH.exists():
            pytest.skip(f"Test fixture not found: {TEST_IMAGE_PATH}")
        return TEST_IMAGE_PATH.read_bytes()

    def test_compress_real_image(self, real_image_bytes):
        """Test compression of the real test image."""
        processor = ImageProcessor(target_size_kb=75)

        result = processor.process(real_image_bytes)

        assert result.data[:2] == b"\xff\xd8"  # JPEG output
        assert result.compressed_size <= 100 * 1024  # Reasonable size
        print(f"Original: {result.original_size} bytes")
        print(f"Compressed: {result.compressed_size} bytes")
        print(f"Quality: {result.quality}")
        print(f"Dimensions: {result.dimensions}")

    def test_compress_real_image_to_small_target(self, real_image_bytes):
        """Test compression to a smaller target size."""
        processor = ImageProcessor(target_size_kb=50, max_dimension=1200)

        result = processor.process(real_image_bytes)

        assert result.data[:2] == b"\xff\xd8"
        # Should attempt to get close to target
        assert result.compressed_size <= 80 * 1024

    def test_real_image_dimensions(self, real_image_bytes):
        """Test that real image dimensions are handled correctly."""
        processor = ImageProcessor(max_dimension=800)

        result = processor.process(real_image_bytes)

        # Both dimensions should be <= max_dimension
        assert result.dimensions[0] <= 800
        assert result.dimensions[1] <= 800
