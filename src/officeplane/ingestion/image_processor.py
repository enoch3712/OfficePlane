"""Image processing utilities for document ingestion.

Provides compression and resizing to optimize images for vision model analysis
while preserving text readability.
"""

import io
from dataclasses import dataclass
from typing import Tuple

from PIL import Image


@dataclass
class ProcessedImage:
    """Result of image processing.

    Attributes:
        data: Compressed image bytes (JPEG format).
        original_size: Size of the original image in bytes.
        compressed_size: Size of the compressed image in bytes.
        dimensions: (width, height) of the processed image.
        quality: JPEG quality level used (1-100).
    """

    data: bytes
    original_size: int
    compressed_size: int
    dimensions: Tuple[int, int]
    quality: int


class ImageProcessor:
    """Processes images for optimal vision model consumption.

    Uses binary search on JPEG quality to achieve target file size while
    preserving text readability.
    """

    def __init__(
        self,
        target_size_kb: int = 75,
        max_dimension: int = 1600,
        min_quality: int = 20,
        max_quality: int = 95,
    ):
        """Initialize the image processor.

        Args:
            target_size_kb: Target file size in kilobytes.
            max_dimension: Maximum width or height in pixels.
            min_quality: Minimum JPEG quality (1-100).
            max_quality: Maximum JPEG quality (1-100).
        """
        self.target_size_bytes = target_size_kb * 1024
        self.max_dimension = max_dimension
        self.min_quality = min_quality
        self.max_quality = max_quality

    def process(self, image_bytes: bytes) -> ProcessedImage:
        """Process an image to meet size constraints.

        Args:
            image_bytes: Raw image bytes (PNG, JPEG, etc.).

        Returns:
            ProcessedImage with compressed data and metadata.
        """
        original_size = len(image_bytes)

        # Load image
        img = Image.open(io.BytesIO(image_bytes))

        # Convert to RGB if necessary (handles PNG with transparency)
        if img.mode in ("RGBA", "P", "LA"):
            # Create white background for transparent images
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        # Resize if necessary
        img = self._resize_if_needed(img)

        # Binary search for optimal quality
        data, quality = self._compress_to_target(img)

        return ProcessedImage(
            data=data,
            original_size=original_size,
            compressed_size=len(data),
            dimensions=img.size,
            quality=quality,
        )

    def _resize_if_needed(self, img: Image.Image) -> Image.Image:
        """Resize image if it exceeds max_dimension.

        Args:
            img: PIL Image to potentially resize.

        Returns:
            Resized image or original if no resize needed.
        """
        width, height = img.size

        if width <= self.max_dimension and height <= self.max_dimension:
            return img

        # Calculate scale factor to fit within max_dimension
        scale = min(self.max_dimension / width, self.max_dimension / height)
        new_width = int(width * scale)
        new_height = int(height * scale)

        return img.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def _compress_to_target(self, img: Image.Image) -> Tuple[bytes, int]:
        """Binary search for JPEG quality to hit target size.

        Args:
            img: PIL Image to compress.

        Returns:
            Tuple of (compressed bytes, quality used).
        """
        # First try max quality
        high_quality_data = self._compress(img, self.max_quality)
        if len(high_quality_data) <= self.target_size_bytes:
            return high_quality_data, self.max_quality

        # Binary search for optimal quality
        low = self.min_quality
        high = self.max_quality
        best_data = high_quality_data
        best_quality = self.max_quality

        while low <= high:
            mid = (low + high) // 2
            data = self._compress(img, mid)
            size = len(data)

            if size <= self.target_size_bytes:
                # This quality works, try higher quality
                best_data = data
                best_quality = mid
                low = mid + 1
            else:
                # Too large, need lower quality
                high = mid - 1

        # If even min quality is too large, return min quality result
        if len(best_data) > self.target_size_bytes and best_quality > self.min_quality:
            best_data = self._compress(img, self.min_quality)
            best_quality = self.min_quality

        return best_data, best_quality

    def _compress(self, img: Image.Image, quality: int) -> bytes:
        """Compress image to JPEG with specified quality.

        Args:
            img: PIL Image to compress.
            quality: JPEG quality (1-100).

        Returns:
            Compressed image bytes.
        """
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=quality, optimize=True)
        return buffer.getvalue()


def compress_image(
    image_bytes: bytes,
    target_size_kb: int = 75,
    max_dimension: int = 1600,
) -> bytes:
    """Convenience function to compress an image.

    Args:
        image_bytes: Raw image bytes.
        target_size_kb: Target file size in KB.
        max_dimension: Maximum width or height.

    Returns:
        Compressed JPEG bytes.
    """
    processor = ImageProcessor(target_size_kb=target_size_kb, max_dimension=max_dimension)
    result = processor.process(image_bytes)
    return result.data
