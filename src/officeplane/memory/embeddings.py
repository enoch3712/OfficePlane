"""
Embedding generation using OpenAI's text-embedding-ada-002.

Provides both sync and async interfaces for generating embeddings
from text content.
"""

from __future__ import annotations

import logging
import os
from typing import List, Optional, cast

log = logging.getLogger("officeplane.memory.embeddings")

# Model configuration
EMBEDDING_MODEL = "text-embedding-ada-002"
EMBEDDING_DIMENSIONS = 1536


class EmbeddingClient:
    """
    Client for generating embeddings via OpenAI API.

    Usage:
        client = EmbeddingClient()
        embedding = await client.embed("Hello world")
        embeddings = await client.embed_batch(["Hello", "World"])
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = EMBEDDING_MODEL,
    ) -> None:
        """
        Initialize the embedding client.

        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Embedding model to use
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model
        self._client: Optional[object] = None

        if not self.api_key:
            log.warning("OPENAI_API_KEY not set - embeddings will fail")

    def _get_client(self) -> object:
        """Lazy-load the OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError(
                    "openai package not installed. "
                    "Install with: pip install openai"
                )
        return self._client

    async def _get_async_client(self) -> object:
        """Lazy-load the async OpenAI client."""
        try:
            from openai import AsyncOpenAI
            return AsyncOpenAI(api_key=self.api_key)
        except ImportError:
            raise ImportError(
                "openai package not installed. "
                "Install with: pip install openai"
            )

    def embed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text (sync).

        Args:
            text: Text to embed

        Returns:
            List of floats (embedding vector)
        """
        client = self._get_client()
        response = client.embeddings.create(  # type: ignore
            model=self.model,
            input=text,
        )
        return cast(List[float], response.data[0].embedding)

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (sync).

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        client = self._get_client()
        response = client.embeddings.create(  # type: ignore
            model=self.model,
            input=texts,
        )
        # Sort by index to maintain order
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]

    async def aembed(self, text: str) -> List[float]:
        """
        Generate embedding for a single text (async).

        Args:
            text: Text to embed

        Returns:
            List of floats (embedding vector)
        """
        client = await self._get_async_client()
        response = await client.embeddings.create(  # type: ignore
            model=self.model,
            input=text,
        )
        return cast(List[float], response.data[0].embedding)

    async def aembed_batch(self, texts: List[str]) -> List[List[float]]:
        """
        Generate embeddings for multiple texts (async).

        Args:
            texts: List of texts to embed

        Returns:
            List of embedding vectors
        """
        if not texts:
            return []

        client = await self._get_async_client()
        response = await client.embeddings.create(  # type: ignore
            model=self.model,
            input=texts,
        )
        sorted_data = sorted(response.data, key=lambda x: x.index)
        return [item.embedding for item in sorted_data]


# Module-level convenience functions with singleton client
_client: Optional[EmbeddingClient] = None


def _get_default_client() -> EmbeddingClient:
    """Get or create the default embedding client."""
    global _client
    if _client is None:
        _client = EmbeddingClient()
    return _client


def get_embedding(text: str) -> List[float]:
    """
    Generate embedding for a single text using default client.

    Args:
        text: Text to embed

    Returns:
        Embedding vector
    """
    return _get_default_client().embed(text)


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for multiple texts using default client.

    Args:
        texts: Texts to embed

    Returns:
        List of embedding vectors
    """
    return _get_default_client().embed_batch(texts)


async def aget_embedding(text: str) -> List[float]:
    """Async version of get_embedding."""
    return await _get_default_client().aembed(text)


async def aget_embeddings(texts: List[str]) -> List[List[float]]:
    """Async version of get_embeddings."""
    return await _get_default_client().aembed_batch(texts)
