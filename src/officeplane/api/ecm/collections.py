"""ECM Collections — folders/workspaces backed by Postgres.

Supports nesting via parent_id and many-to-many with Documents.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, HTTPException
from prisma import Json, Prisma
from pydantic import BaseModel

router = APIRouter(prefix="/api/ecm/collections", tags=["ecm:collections"])


class CreateCollectionRequest(BaseModel):
    name: str
    description: Optional[str] = None
    parent_id: Optional[str] = None
    metadata: Optional[dict] = None


class UpdateCollectionRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    parent_id: Optional[str] = None


class AddDocumentRequest(BaseModel):
    document_id: str


def _serialize_collection(c, *, document_count: int = 0, child_count: int = 0) -> dict:
    return {
        "collection_id": str(c.id),
        "name": c.name,
        "description": c.description,
        "parent_id": str(c.parentId) if c.parentId else None,
        "document_count": document_count,
        "child_count": child_count,
        "metadata": c.metadata,
        "created_at": c.createdAt.isoformat(),
        "updated_at": c.updatedAt.isoformat(),
    }


@router.get("")
async def list_collections(parent_id: Optional[str] = None):
    db = Prisma()
    await db.connect()
    try:
        where = {"parentId": parent_id} if parent_id else {"parentId": None}
        rows = await db.collection.find_many(where=where, order={"name": "asc"})
        items = []
        for c in rows:
            doc_count = await db.documentcollection.count(where={"collectionId": c.id})
            child_count = await db.collection.count(where={"parentId": c.id})
            items.append(_serialize_collection(c, document_count=doc_count, child_count=child_count))
        return {"collections": items}
    finally:
        await db.disconnect()


@router.post("", status_code=201)
async def create_collection(request: CreateCollectionRequest):
    db = Prisma()
    await db.connect()
    try:
        data = {
            "name": request.name,
            "description": request.description,
        }
        if request.parent_id:
            data["parentId"] = request.parent_id
        if request.metadata:
            data["metadata"] = Json(request.metadata)
        c = await db.collection.create(data=data)
        return _serialize_collection(c)
    finally:
        await db.disconnect()


@router.get("/{collection_id}")
async def get_collection(collection_id: str):
    db = Prisma()
    await db.connect()
    try:
        c = await db.collection.find_unique(where={"id": collection_id})
        if not c:
            raise HTTPException(status_code=404, detail="Collection not found")
        doc_count = await db.documentcollection.count(where={"collectionId": c.id})
        child_count = await db.collection.count(where={"parentId": c.id})
        return _serialize_collection(c, document_count=doc_count, child_count=child_count)
    finally:
        await db.disconnect()


@router.put("/{collection_id}")
async def update_collection(collection_id: str, request: UpdateCollectionRequest):
    db = Prisma()
    await db.connect()
    try:
        existing = await db.collection.find_unique(where={"id": collection_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Collection not found")
        data = {}
        if request.name is not None:
            data["name"] = request.name
        if request.description is not None:
            data["description"] = request.description
        if request.parent_id is not None:
            data["parentId"] = request.parent_id
        c = await db.collection.update(where={"id": collection_id}, data=data)
        return _serialize_collection(c)
    finally:
        await db.disconnect()


@router.delete("/{collection_id}", status_code=204)
async def delete_collection(collection_id: str):
    db = Prisma()
    await db.connect()
    try:
        existing = await db.collection.find_unique(where={"id": collection_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Collection not found")
        await db.collection.delete(where={"id": collection_id})
        return None
    finally:
        await db.disconnect()


@router.get("/{collection_id}/documents")
async def list_collection_documents(collection_id: str, limit: int = 50, offset: int = 0):
    db = Prisma()
    await db.connect()
    try:
        existing = await db.collection.find_unique(where={"id": collection_id})
        if not existing:
            raise HTTPException(status_code=404, detail="Collection not found")
        links = await db.documentcollection.find_many(
            where={"collectionId": collection_id},
            include={"document": True},
            order={"addedAt": "desc"},
            take=limit,
            skip=offset,
        )
        total = await db.documentcollection.count(where={"collectionId": collection_id})
        documents = [
            {
                "document_id": str(link.document.id),
                "title": link.document.title,
                "summary": link.document.summary,
                "topics": link.document.topics,
                "added_at": link.addedAt.isoformat(),
            }
            for link in links
            if link.document is not None
        ]
        return {
            "collection_id": collection_id,
            "documents": documents,
            "total": total,
            "limit": limit,
            "offset": offset,
        }
    finally:
        await db.disconnect()


@router.post("/{collection_id}/documents", status_code=201)
async def add_document_to_collection(collection_id: str, request: AddDocumentRequest):
    db = Prisma()
    await db.connect()
    try:
        coll = await db.collection.find_unique(where={"id": collection_id})
        if not coll:
            raise HTTPException(status_code=404, detail="Collection not found")
        doc = await db.document.find_unique(where={"id": request.document_id})
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        link = await db.documentcollection.upsert(
            where={
                "documentId_collectionId": {
                    "documentId": request.document_id,
                    "collectionId": collection_id,
                }
            },
            data={
                "create": {
                    "documentId": request.document_id,
                    "collectionId": collection_id,
                },
                "update": {},
            },
        )
        return {
            "collection_id": collection_id,
            "document_id": request.document_id,
            "added_at": link.addedAt.isoformat(),
        }
    finally:
        await db.disconnect()


@router.delete("/{collection_id}/documents/{document_id}", status_code=204)
async def remove_document_from_collection(collection_id: str, document_id: str):
    db = Prisma()
    await db.connect()
    try:
        try:
            await db.documentcollection.delete(
                where={
                    "documentId_collectionId": {
                        "documentId": document_id,
                        "collectionId": collection_id,
                    }
                }
            )
        except Exception:
            raise HTTPException(status_code=404, detail="Link not found")
        return None
    finally:
        await db.disconnect()
