"""Pluggable embedding provider.

Selected by env OFFICEPLANE_EMBEDDING_PROVIDER (default: gemini).
- gemini: Google gemini-embedding-001, 768 dim (truncated via output_dimensionality)
- openai: text-embedding-3-small (compat slot), 1536 dim — requires OPENAI_API_KEY
- none: raises if used (used in tests with mocking)
"""
from __future__ import annotations

import os
from abc import ABC, abstractmethod

_GEMINI_OUTPUT_DIMS = 768


class EmbeddingProvider(ABC):
    @property
    @abstractmethod
    def dimensions(self) -> int: ...

    @abstractmethod
    async def embed_one(self, text: str) -> list[float]: ...

    @abstractmethod
    async def embed_batch(self, texts: list[str]) -> list[list[float]]: ...


class GeminiEmbeddingProvider(EmbeddingProvider):
    """Google Gemini embedding provider using gemini-embedding-001 with 768-dim output."""

    def __init__(self, model: str = "gemini-embedding-001"):
        self._model = model
        self._key = os.getenv("GOOGLE_API_KEY")
        if not self._key:
            raise RuntimeError("GOOGLE_API_KEY required for Gemini embeddings")

    @property
    def dimensions(self) -> int:
        return _GEMINI_OUTPUT_DIMS

    async def embed_one(self, text: str) -> list[float]:
        return (await self.embed_batch([text]))[0]

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        import asyncio

        import google.genai as genai
        from google.genai import types

        client = genai.Client(api_key=self._key)
        embed_config = types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=_GEMINI_OUTPUT_DIMS,
        )

        def _call() -> list[list[float]]:
            out = []
            for t in texts:
                r = client.models.embed_content(
                    model=self._model,
                    contents=t,
                    config=embed_config,
                )
                out.append(list(r.embeddings[0].values))
            return out

        return await asyncio.get_event_loop().run_in_executor(None, _call)


def get_embedding_provider() -> EmbeddingProvider:
    name = (os.getenv("OFFICEPLANE_EMBEDDING_PROVIDER") or "gemini").lower()
    if name == "gemini":
        return GeminiEmbeddingProvider()
    # extend later
    raise RuntimeError(f"unknown embedding provider: {name}")
