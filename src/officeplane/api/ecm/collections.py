"""
ECM Collections routes — [MOCK]

Collections are folders/workspaces that organize documents.
Supports nesting via parent_id.

GET    /api/ecm/collections
POST   /api/ecm/collections
GET    /api/ecm/collections/{id}
PUT    /api/ecm/collections/{id}
DELETE /api/ecm/collections/{id}
GET    /api/ecm/collections/{id}/documents
POST   /api/ecm/collections/{id}/documents
DELETE /api/ecm/collections/{id}/documents/{doc_id}
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/api/ecm/collections", tags=["ecm:collections"])

_MOCK = True


class CreateCollectionRequest(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[str] = None


class UpdateCollectionRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class AddDocumentRequest(BaseModel):
    document_id: str


@router.get("")
async def list_collections(parent_id: Optional[str] = None):
    return {
        "collections": [
            {
                "collection_id": "col_001",
                "name": "Finance",
                "description": "Finance department documents",
                "parent_id": None,
                "document_count": 14,
                "child_count": 2,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            {
                "collection_id": "col_002",
                "name": "Q4 Reports",
                "description": "Q4 reporting documents",
                "parent_id": "col_001",
                "document_count": 5,
                "child_count": 0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
        ],
        "_mock": _MOCK,
    }


@router.post("", status_code=201)
async def create_collection(request: CreateCollectionRequest):
    return {
        "collection_id": f"col_{uuid4().hex[:8]}",
        "name": request.name,
        "description": request.description,
        "parent_id": request.parent_id,
        "document_count": 0,
        "child_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }


@router.get("/{collection_id}")
async def get_collection(collection_id: str):
    return {
        "collection_id": collection_id,
        "name": "Mock Collection",
        "description": "A mock collection",
        "parent_id": None,
        "document_count": 7,
        "child_count": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }


@router.put("/{collection_id}")
async def update_collection(collection_id: str, request: UpdateCollectionRequest):
    return {
        "collection_id": collection_id,
        "name": request.name or "Mock Collection",
        "description": request.description,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(collection_id: str):
    return None


@router.get("/{collection_id}/documents")
async def list_collection_documents(collection_id: str, limit: int = 20, offset: int = 0):
    return {
        "collection_id": collection_id,
        "documents": [
            {
                "document_id": f"doc_00{i}",
                "title": f"Mock Document {i}",
                "status": "published",
                "added_at": datetime.now(timezone.utc).isoformat(),
            }
            for i in range(1, 4)
        ],
        "total": 3,
        "limit": limit,
        "offset": offset,
        "_mock": _MOCK,
    }


@router.post("/{collection_id}/documents", status_code=201)
async def add_document_to_collection(collection_id: str, request: AddDocumentRequest):
    return {
        "collection_id": collection_id,
        "document_id": request.document_id,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "_mock": _MOCK,
    }


@router.delete("/{collection_id}/documents/{document_id}", status_code=204)
async def remove_document_from_collection(collection_id: str, document_id: str):
    return None
