"""Configuration for document ingestion."""

import os
from dataclasses import dataclass, field
from typing import Literal


@dataclass
class IngestionConfig:
    """Configuration for the document ingestion service.

    All settings can be overridden via environment variables with the
    OFFICEPLANE_INGESTION_ prefix.

    Attributes:
        mode: Ingestion mode — "text" (default, DeepSeek text path) or "vision".
        ingestion_model: LiteLLM model string used in text mode.
        vision_provider: Vision model provider ("gemini" or "mock"). Used only in vision mode.
        vision_model: Model name for the vision provider.
        google_api_key: API key for Gemini (from GOOGLE_API_KEY env var).
        image_size_kb: Target size for compressed images in KB.
        pdf_dpi: DPI for rendering PDF pages to images.
        batch_size: Number of pages to process per vision API call.
        auto_index: Whether to automatically index documents for RAG.
        max_images_per_call: Maximum images per vision API call (provider dependent).
    """

    mode: str = field(default_factory=lambda: _env_str(
        "OFFICEPLANE_INGESTION_MODE", "text"
    ))
    ingestion_model: str = field(default_factory=lambda: _env_str(
        "OFFICEPLANE_INGESTION_MODEL", "deepseek/deepseek-v4-flash"
    ))
    vision_provider: Literal["gemini", "mock"] = field(default_factory=lambda: _env_str(
        "OFFICEPLANE_INGESTION_VISION_PROVIDER", "gemini"
    ))
    vision_model: str = field(default_factory=lambda: _env_str(
        "OFFICEPLANE_INGESTION_VISION_MODEL", "gemini-3-flash-preview"
    ))
    google_api_key: str = field(default_factory=lambda: _env_str(
        "GOOGLE_API_KEY", ""
    ) or _env_str("GEMINI_API_KEY", ""))
    image_size_kb: int = field(default_factory=lambda: _env_int(
        "OFFICEPLANE_INGESTION_IMAGE_SIZE_KB", 75
    ))
    pdf_dpi: int = field(default_factory=lambda: _env_int(
        "OFFICEPLANE_INGESTION_PDF_DPI", 150
    ))
    batch_size: int = field(default_factory=lambda: _env_int(
        "OFFICEPLANE_INGESTION_BATCH_SIZE", 8
    ))
    auto_index: bool = field(default_factory=lambda: _env_bool(
        "OFFICEPLANE_INGESTION_INDEX", True
    ))
    max_images_per_call: int = field(default_factory=lambda: _env_int(
        "OFFICEPLANE_INGESTION_MAX_IMAGES", 16
    ))

    def validate(self) -> None:
        """Validate configuration values.

        Raises:
            ValueError: If any configuration value is invalid.
        """
        if self.mode not in ("text", "vision"):
            raise ValueError(f"Invalid mode: {self.mode}. Must be 'text' or 'vision'")

        # Vision-specific validations only apply when mode == "vision"
        if self.mode == "vision":
            if self.vision_provider not in ("gemini", "mock"):
                raise ValueError(f"Invalid vision_provider: {self.vision_provider}")

            if self.vision_provider == "gemini" and not self.google_api_key:
                raise ValueError("GOOGLE_API_KEY is required when using gemini provider")

        if self.image_size_kb < 10 or self.image_size_kb > 500:
            raise ValueError(f"image_size_kb must be between 10 and 500, got {self.image_size_kb}")

        if self.pdf_dpi < 72 or self.pdf_dpi > 300:
            raise ValueError(f"pdf_dpi must be between 72 and 300, got {self.pdf_dpi}")

        if self.batch_size < 1 or self.batch_size > 32:
            raise ValueError(f"batch_size must be between 1 and 32, got {self.batch_size}")


def _env_str(key: str, default: str) -> str:
    """Get string from environment variable."""
    return os.environ.get(key, default)


def _env_int(key: str, default: int) -> int:
    """Get integer from environment variable."""
    value = os.environ.get(key)
    if value is None:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def _env_bool(key: str, default: bool) -> bool:
    """Get boolean from environment variable."""
    value = os.environ.get(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")
