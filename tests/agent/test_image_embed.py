"""Tests for image_embed and image_provider (Phase 11.8)."""
import asyncio
from pathlib import Path
from unittest.mock import patch
import pytest

from officeplane.content_agent.image_embed import resolve_figure_image
from officeplane.content_agent.image_provider import PlaceholderProvider, get_provider
from officeplane.content_agent.renderers.document import Figure


def test_resolve_uses_existing_src(tmp_path):
    img = tmp_path / "x.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\0" * 100)
    fig = Figure(id="f1", src=str(img))
    p = resolve_figure_image(fig, tmp_path)
    assert p == img


def test_resolve_returns_none_when_no_src_no_prompt(tmp_path):
    fig = Figure(id="f1")
    assert resolve_figure_image(fig, tmp_path) is None


def test_resolve_generates_via_placeholder(tmp_path, monkeypatch):
    monkeypatch.setenv("OFFICEPLANE_IMAGE_PROVIDER", "placeholder")
    fig = Figure(id="fig-A", prompt="diagram of a BP cuff")
    p = resolve_figure_image(fig, tmp_path)
    assert p is not None and p.exists()
    assert p.name == "fig-A.png"
    assert p.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_provider_factory_defaults_to_placeholder(monkeypatch):
    monkeypatch.delenv("OFFICEPLANE_IMAGE_PROVIDER", raising=False)
    assert isinstance(get_provider(), PlaceholderProvider)


def test_provider_factory_picks_gemini(monkeypatch):
    monkeypatch.setenv("OFFICEPLANE_IMAGE_PROVIDER", "gemini")
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy")
    from officeplane.content_agent.image_provider import GeminiImageProvider
    assert isinstance(get_provider(), GeminiImageProvider)
