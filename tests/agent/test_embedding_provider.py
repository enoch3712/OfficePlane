import pytest
from officeplane.memory.embedding_provider import GeminiEmbeddingProvider, get_embedding_provider


def test_gemini_provider_requires_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GOOGLE_API_KEY"):
        GeminiEmbeddingProvider()


def test_gemini_dimensions(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy")
    p = GeminiEmbeddingProvider()
    assert p.dimensions == 768


def test_provider_factory_default(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "dummy")
    monkeypatch.delenv("OFFICEPLANE_EMBEDDING_PROVIDER", raising=False)
    p = get_embedding_provider()
    assert isinstance(p, GeminiEmbeddingProvider)
