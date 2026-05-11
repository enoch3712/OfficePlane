"""Pluggable OCR provider.

Selected by env OFFICEPLANE_OCR_PROVIDER (default: tesseract).
- tesseract: pytesseract wrapper around the tesseract CLI. Requires tesseract to be
  installed in the container (apt: tesseract-ocr).
- none: raises RuntimeError. Used in tests where OCR shouldn't actually run.

TODO: Add tesseract-ocr to the Dockerfile so future image rebuilds include it:
  RUN apt-get update && apt-get install -y tesseract-ocr && rm -rf /var/lib/apt/lists/*
"""
from __future__ import annotations

import logging
import os
from abc import ABC, abstractmethod
from io import BytesIO

log = logging.getLogger("officeplane.ingestion.ocr")


class OCRProvider(ABC):
    @abstractmethod
    def extract_text(self, image_bytes: bytes, *, lang: str = "eng") -> str: ...

    @property
    @abstractmethod
    def available(self) -> bool: ...


class TesseractProvider(OCRProvider):
    def __init__(self):
        self._verified = None  # cache the availability check

    @property
    def available(self) -> bool:
        if self._verified is None:
            try:
                import pytesseract  # noqa: F401
                # Run a smoke version check
                v = pytesseract.get_tesseract_version()
                log.info("tesseract %s available", v)
                self._verified = True
            except Exception as e:
                log.warning("tesseract not available: %s", e)
                self._verified = False
        return self._verified

    def extract_text(self, image_bytes: bytes, *, lang: str = "eng") -> str:
        if not self.available:
            raise RuntimeError("tesseract OCR is not available in this environment")
        import pytesseract
        from PIL import Image
        img = Image.open(BytesIO(image_bytes))
        # Convert non-RGB modes that tesseract chokes on
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        return pytesseract.image_to_string(img, lang=lang)


class NoOpProvider(OCRProvider):
    @property
    def available(self) -> bool:
        return False

    def extract_text(self, image_bytes: bytes, *, lang: str = "eng") -> str:
        raise RuntimeError("OCR provider disabled (OFFICEPLANE_OCR_PROVIDER=none)")


def get_ocr_provider() -> OCRProvider:
    name = (os.getenv("OFFICEPLANE_OCR_PROVIDER") or "tesseract").lower()
    if name == "tesseract":
        return TesseractProvider()
    if name == "none":
        return NoOpProvider()
    raise RuntimeError(f"unknown OCR provider: {name}")
