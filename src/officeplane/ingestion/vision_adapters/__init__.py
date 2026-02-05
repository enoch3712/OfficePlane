"""Vision model adapters for document structure extraction."""

from officeplane.ingestion.vision_adapters.gemini import GeminiVisionAdapter
from officeplane.ingestion.vision_adapters.mock import MockVisionAdapter

__all__ = [
    "GeminiVisionAdapter",
    "MockVisionAdapter",
]
