"""
ECM Search routes — [MOCK]

Full-text + metadata search, and semantic similarity via existing vector store.

GET /api/ecm/search?q=...
GET /api/ecm/documents/{id}/similar
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Query
from pydantic import BaseModel

router = APIRouter(prefix="/api/ecm", tags=["ecm:search"])

_MOCK = True


@router.get("/search")
async def search(
    q: str = Query(..., description="Full-text search query"),
    document_type: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    collection_id: Optional[str] = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
):
    return {
        "query": q,
        "filters": {
            "document_type": document_type,
            "status": status,
            "collection_id": collection_id,
        },
        "results": [
            {
                "document_id": f"doc_00{i}",
                "title": f"Mock Result {i} for '{q}'",
                "document_type": "report",
                "status": "published",
                "score": round(0.95 - i * 0.1, 2),
                "snippet": f"...relevant excerpt matching '{q}'...",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
            for i in range(1, 4)
        ],
        "total": 3,
        "limit": limit,
        "offset": offset,
        "_mock": _MOCK,
    }


@router.get("/documents/{document_id}/similar")
async def get_similar_documents(document_id: str, limit: int = Query(5, le=20)):
    return {
        "document_id": document_id,
        "similar": [
            {
                "document_id": f"doc_sim_{i}",
                "title": f"Similar Document {i}",
                "similarity_score": round(0.92 - i * 0.07, 2),
                "document_type": "report",
                "status": "published",
            }
            for i in range(1, limit + 1)
        ],
        "_mock": _MOCK,
    }
