"""
OfficePlane Memory System

Provides RAG (Retrieval Augmented Generation) capabilities:
- embeddings: OpenAI embedding generation
- vector_store: pgvector storage and search
- rag: High-level retrieval utilities
"""

from officeplane.memory.embeddings import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EmbeddingClient,
    aget_embedding,
    aget_embeddings,
    get_embedding,
    get_embeddings,
)
from officeplane.memory.vector_store import (
    ChunkRecord,
    SearchResult,
    VectorStore,
)
try:
    from officeplane.memory.rag import (
        DocumentIndexer,
        RAGResult,
        RAGRetriever,
        get_indexer,
        get_retriever,
        search,
    )
except ImportError:
    pass  # Circular import guard — rag is available when accessed directly

__all__ = [
    # Embeddings
    "EmbeddingClient",
    "get_embedding",
    "get_embeddings",
    "aget_embedding",
    "aget_embeddings",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIMENSIONS",
    # Vector Store
    "VectorStore",
    "ChunkRecord",
    "SearchResult",
    # RAG
    "RAGRetriever",
    "RAGResult",
    "DocumentIndexer",
    "get_retriever",
    "get_indexer",
    "search",
]
