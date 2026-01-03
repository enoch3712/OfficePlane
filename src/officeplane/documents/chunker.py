"""
Text chunking with sliding window for RAG.

Splits text into overlapping chunks for optimal embedding and retrieval.
Uses tiktoken for accurate token counting with OpenAI models.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional

log = logging.getLogger("officeplane.documents.chunker")

# Default configuration
DEFAULT_CHUNK_SIZE = 500  # tokens
DEFAULT_CHUNK_OVERLAP = 100  # tokens
DEFAULT_MIN_CHUNK_SIZE = 50  # minimum tokens per chunk


@dataclass
class TextChunk:
    """A chunk of text with metadata."""

    text: str
    start_offset: int  # Character offset in original text
    end_offset: int
    token_count: int


class SlidingWindowChunker:
    """
    Splits text into overlapping chunks using a sliding window.

    Uses tiktoken for accurate token counting compatible with OpenAI models.

    Usage:
        chunker = SlidingWindowChunker(chunk_size=500, overlap=100)
        chunks = chunker.chunk(long_text)
    """

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        overlap: int = DEFAULT_CHUNK_OVERLAP,
        min_chunk_size: int = DEFAULT_MIN_CHUNK_SIZE,
        encoding_name: str = "cl100k_base",  # GPT-4 / ada-002 encoding
    ) -> None:
        """
        Initialize the chunker.

        Args:
            chunk_size: Target number of tokens per chunk
            overlap: Number of overlapping tokens between chunks
            min_chunk_size: Minimum tokens for a chunk to be created
            encoding_name: tiktoken encoding name
        """
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.min_chunk_size = min_chunk_size
        self.encoding_name = encoding_name
        self._encoder: Optional[object] = None

    def _get_encoder(self) -> object:
        """Lazy-load the tiktoken encoder."""
        if self._encoder is None:
            try:
                import tiktoken
                self._encoder = tiktoken.get_encoding(self.encoding_name)
            except ImportError:
                raise ImportError(
                    "tiktoken not installed. Install with: pip install tiktoken"
                )
        return self._encoder

    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        encoder = self._get_encoder()
        return len(encoder.encode(text))  # type: ignore

    def chunk(self, text: str) -> List[TextChunk]:
        """
        Split text into overlapping chunks.

        Args:
            text: Text to chunk

        Returns:
            List of TextChunk objects
        """
        if not text or not text.strip():
            return []

        encoder = self._get_encoder()
        tokens = encoder.encode(text)  # type: ignore
        total_tokens = len(tokens)

        if total_tokens <= self.chunk_size:
            # Text fits in one chunk
            return [
                TextChunk(
                    text=text,
                    start_offset=0,
                    end_offset=len(text),
                    token_count=total_tokens,
                )
            ]

        chunks = []
        start_token = 0

        while start_token < total_tokens:
            # Determine chunk boundaries
            end_token = min(start_token + self.chunk_size, total_tokens)

            # Get the tokens for this chunk
            chunk_tokens = tokens[start_token:end_token]

            # Decode back to text
            chunk_text = encoder.decode(chunk_tokens)  # type: ignore

            # Calculate character offsets
            # This is approximate - we find where the chunk text appears
            if start_token == 0:
                start_char = 0
            else:
                # Find the overlap text and locate it
                prefix_tokens = tokens[:start_token]
                prefix_text = encoder.decode(prefix_tokens)  # type: ignore
                start_char = len(prefix_text)

            end_char = start_char + len(chunk_text)

            # Skip if chunk is too small (except for the last chunk)
            if len(chunk_tokens) >= self.min_chunk_size or end_token == total_tokens:
                chunks.append(
                    TextChunk(
                        text=chunk_text,
                        start_offset=start_char,
                        end_offset=end_char,
                        token_count=len(chunk_tokens),
                    )
                )

            # Move window forward
            if end_token >= total_tokens:
                break

            # Advance by (chunk_size - overlap) tokens
            start_token = start_token + self.chunk_size - self.overlap

        return chunks

    def chunk_by_paragraphs(self, text: str) -> List[TextChunk]:
        """
        Split text by paragraphs, then combine into chunks.

        Tries to keep paragraphs together when possible.

        Args:
            text: Text to chunk

        Returns:
            List of TextChunk objects
        """
        if not text or not text.strip():
            return []

        # Split by double newlines (paragraphs)
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        if not paragraphs:
            return []

        encoder = self._get_encoder()
        chunks = []
        current_text = ""
        current_start = 0
        current_tokens = 0

        for i, para in enumerate(paragraphs):
            para_tokens = len(encoder.encode(para))  # type: ignore

            # If single paragraph exceeds chunk size, use sliding window on it
            if para_tokens > self.chunk_size:
                # Flush current chunk first
                if current_text:
                    chunks.append(
                        TextChunk(
                            text=current_text.strip(),
                            start_offset=current_start,
                            end_offset=current_start + len(current_text),
                            token_count=current_tokens,
                        )
                    )
                    current_text = ""
                    current_tokens = 0

                # Chunk the long paragraph
                para_start = text.find(para)
                para_chunks = self.chunk(para)
                for pc in para_chunks:
                    pc.start_offset += para_start
                    pc.end_offset += para_start
                    chunks.append(pc)

                # Update start for next chunk
                current_start = para_start + len(para)
                continue

            # Would adding this paragraph exceed the limit?
            separator = "\n\n" if current_text else ""
            new_text = current_text + separator + para
            new_tokens = current_tokens + para_tokens + (2 if current_text else 0)

            if new_tokens > self.chunk_size and current_text:
                # Flush current chunk
                chunks.append(
                    TextChunk(
                        text=current_text.strip(),
                        start_offset=current_start,
                        end_offset=current_start + len(current_text),
                        token_count=current_tokens,
                    )
                )
                # Start new chunk with this paragraph
                current_start = text.find(para)
                current_text = para
                current_tokens = para_tokens
            else:
                # Add to current chunk
                if not current_text:
                    current_start = text.find(para)
                current_text = new_text
                current_tokens = new_tokens

        # Flush remaining
        if current_text and current_tokens >= self.min_chunk_size:
            chunks.append(
                TextChunk(
                    text=current_text.strip(),
                    start_offset=current_start,
                    end_offset=current_start + len(current_text),
                    token_count=current_tokens,
                )
            )

        return chunks


# Module-level convenience function
_chunker: Optional[SlidingWindowChunker] = None


def get_chunker() -> SlidingWindowChunker:
    """Get the default chunker instance."""
    global _chunker
    if _chunker is None:
        _chunker = SlidingWindowChunker()
    return _chunker


def chunk_text(
    text: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> List[TextChunk]:
    """
    Convenience function to chunk text with default settings.

    Args:
        text: Text to chunk
        chunk_size: Target tokens per chunk
        overlap: Overlap tokens between chunks

    Returns:
        List of TextChunk objects
    """
    chunker = SlidingWindowChunker(chunk_size=chunk_size, overlap=overlap)
    return chunker.chunk(text)
