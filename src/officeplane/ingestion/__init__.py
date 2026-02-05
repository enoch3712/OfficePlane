"""Vision-based document ingestion service.

This module provides document ingestion using vision models to extract
document structure (chapters, sections, pages) from page images.

Imports are lazy to avoid requiring PIL/Pillow unless the ingestion
service is actually used.
"""

from typing import TYPE_CHECKING

# Always import config since it has no heavy dependencies
from officeplane.ingestion.config import IngestionConfig

# Lazy imports for components that require PIL/Pillow
if TYPE_CHECKING:
    from officeplane.ingestion.ingestion_service import (
        IngestionResult,
        VisionIngestionService,
    )
    from officeplane.ingestion.vision_protocol import VisionModelProtocol, VisionResponse

__all__ = [
    "IngestionConfig",
    "IngestionResult",
    "VisionIngestionService",
    "VisionModelProtocol",
    "VisionResponse",
]


def __getattr__(name: str):
    """Lazy import for heavy dependencies."""
    if name == "IngestionResult":
        from officeplane.ingestion.ingestion_service import IngestionResult
        return IngestionResult
    if name == "VisionIngestionService":
        from officeplane.ingestion.ingestion_service import VisionIngestionService
        return VisionIngestionService
    if name == "VisionModelProtocol":
        from officeplane.ingestion.vision_protocol import VisionModelProtocol
        return VisionModelProtocol
    if name == "VisionResponse":
        from officeplane.ingestion.vision_protocol import VisionResponse
        return VisionResponse
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
