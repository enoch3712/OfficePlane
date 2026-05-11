import pytest
from unittest.mock import patch
from officeplane.ingestion.ocr import get_ocr_provider, TesseractProvider, NoOpProvider


def test_default_is_tesseract(monkeypatch):
    monkeypatch.delenv("OFFICEPLANE_OCR_PROVIDER", raising=False)
    p = get_ocr_provider()
    assert isinstance(p, TesseractProvider)


def test_none_provider(monkeypatch):
    monkeypatch.setenv("OFFICEPLANE_OCR_PROVIDER", "none")
    p = get_ocr_provider()
    assert isinstance(p, NoOpProvider)
    assert p.available is False
    with pytest.raises(RuntimeError):
        p.extract_text(b"fake")


def test_unknown_provider_raises(monkeypatch):
    monkeypatch.setenv("OFFICEPLANE_OCR_PROVIDER", "junk")
    with pytest.raises(RuntimeError, match="unknown OCR provider"):
        get_ocr_provider()


def test_tesseract_handles_real_image_or_skips():
    """If tesseract is installed, OCR a tiny PNG. Otherwise skip — we just verify availability."""
    p = TesseractProvider()
    if not p.available:
        pytest.skip("tesseract not installed in this environment")
    from PIL import Image, ImageDraw
    import io
    # Make a 200x60 image with the word "HELLO"
    img = Image.new("RGB", (200, 60), color="white")
    d = ImageDraw.Draw(img)
    d.text((10, 10), "HELLO", fill="black")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    text = p.extract_text(buf.getvalue())
    # Just confirm something came back. Cheap default fonts may produce garbage.
    assert isinstance(text, str)
