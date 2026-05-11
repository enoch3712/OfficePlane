"""Document tag endpoints — CRUD + apply/remove."""
from __future__ import annotations

import logging
import re
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from prisma import Prisma
from pydantic import BaseModel, Field, validator

router = APIRouter(tags=["tags"])
log = logging.getLogger("officeplane.api.tags")


TAG_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")


class CreateTagRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=40)
    color: str | None = "#5EFCAB"
    description: str | None = None

    @validator("name")
    def _kebab(cls, v: str) -> str:
        v2 = v.lower().strip()
        if not TAG_NAME_RE.match(v2):
            raise ValueError("name must be lowercase kebab-case, ≤ 40 chars, e.g. 'monthly-report'")
        return v2


class AddDocTagRequest(BaseModel):
    tag_name: str
    actor: str | None = None


@router.get("/api/tags")
async def list_tags(q: str | None = Query(None)):
    db = Prisma()
    await db.connect()
    try:
        where: dict[str, Any] = {}
        if q:
            where["name"] = {"contains": q.lower()}
        rows = await db.tag.find_many(where=where, order={"name": "asc"})
        # Count usage per tag
        out: list[dict[str, Any]] = []
        for r in rows:
            usage = await db.documenttag.count(where={"tagId": r.id})
            out.append({
                "id": r.id, "name": r.name, "color": r.color,
                "description": r.description, "document_count": usage,
                "created_at": r.createdAt.isoformat() if r.createdAt else None,
            })
        return {"tags": out}
    finally:
        await db.disconnect()


@router.post("/api/tags", status_code=201)
async def create_tag(body: CreateTagRequest):
    db = Prisma()
    await db.connect()
    try:
        existing = await db.tag.find_unique(where={"name": body.name})
        if existing:
            return {"id": existing.id, "name": existing.name, "color": existing.color,
                    "description": existing.description, "created": False}
        tag = await db.tag.create(data={
            "name": body.name, "color": body.color or "#5EFCAB",
            "description": body.description,
        })
        return {"id": tag.id, "name": tag.name, "color": tag.color,
                "description": tag.description, "created": True}
    finally:
        await db.disconnect()


@router.delete("/api/tags/{tag_id}")
async def delete_tag(tag_id: str):
    db = Prisma()
    await db.connect()
    try:
        existing = await db.tag.find_unique(where={"id": tag_id})
        if not existing:
            raise HTTPException(status_code=404, detail="tag not found")
        await db.tag.delete(where={"id": tag_id})
        return {"deleted": tag_id}
    finally:
        await db.disconnect()


@router.get("/api/documents/{document_id}/tags")
async def get_document_tags(document_id: str):
    db = Prisma()
    await db.connect()
    try:
        doc = await db.document.find_unique(where={"id": document_id})
        if not doc:
            raise HTTPException(status_code=404, detail="document not found")
        rows = await db.documenttag.find_many(where={"documentId": document_id})
        tag_ids = [r.tagId for r in rows]
        if not tag_ids:
            return {"document_id": document_id, "tags": []}
        tags = await db.tag.find_many(where={"id": {"in": tag_ids}})
        return {"document_id": document_id, "tags": [
            {"id": t.id, "name": t.name, "color": t.color, "description": t.description}
            for t in tags
        ]}
    finally:
        await db.disconnect()


@router.post("/api/documents/{document_id}/tags", status_code=201)
async def add_document_tag(document_id: str, body: AddDocTagRequest):
    """Apply a tag to a document. Creates the tag if it doesn't exist."""
    name = body.tag_name.lower().strip()
    if not TAG_NAME_RE.match(name):
        raise HTTPException(status_code=400, detail="invalid tag name (kebab-case, ≤40 chars)")
    db = Prisma()
    await db.connect()
    try:
        doc = await db.document.find_unique(where={"id": document_id})
        if not doc:
            raise HTTPException(status_code=404, detail="document not found")
        tag = await db.tag.find_unique(where={"name": name})
        if not tag:
            tag = await db.tag.create(data={"name": name, "color": "#5EFCAB"})
        # Idempotent — upsert via try/except since composite PK
        existing = await db.documenttag.find_unique(
            where={"documentId_tagId": {"documentId": document_id, "tagId": tag.id}}
        )
        if existing:
            return {"document_id": document_id, "tag": {"id": tag.id, "name": tag.name},
                    "added": False}
        await db.documenttag.create(data={
            "documentId": document_id, "tagId": tag.id, "actor": body.actor,
        })
        return {"document_id": document_id, "tag": {"id": tag.id, "name": tag.name, "color": tag.color},
                "added": True}
    finally:
        await db.disconnect()


@router.delete("/api/documents/{document_id}/tags/{tag_name}")
async def remove_document_tag(document_id: str, tag_name: str):
    name = tag_name.lower().strip()
    db = Prisma()
    await db.connect()
    try:
        tag = await db.tag.find_unique(where={"name": name})
        if not tag:
            raise HTTPException(status_code=404, detail="tag not found")
        existing = await db.documenttag.find_unique(
            where={"documentId_tagId": {"documentId": document_id, "tagId": tag.id}}
        )
        if not existing:
            raise HTTPException(status_code=404, detail="document is not tagged with this tag")
        await db.documenttag.delete(
            where={"documentId_tagId": {"documentId": document_id, "tagId": tag.id}}
        )
        return {"removed": True, "document_id": document_id, "tag": tag.name}
    finally:
        await db.disconnect()


@router.get("/api/tags/{tag_name}/documents")
async def list_documents_with_tag(tag_name: str, limit: int = Query(50, ge=1, le=500)):
    name = tag_name.lower().strip()
    db = Prisma()
    await db.connect()
    try:
        tag = await db.tag.find_unique(where={"name": name})
        if not tag:
            raise HTTPException(status_code=404, detail="tag not found")
        rows = await db.documenttag.find_many(
            where={"tagId": tag.id},
            order={"createdAt": "desc"},
            take=limit,
        )
        doc_ids = [r.documentId for r in rows]
        if not doc_ids:
            return {"tag": tag.name, "documents": []}
        docs = await db.document.find_many(where={"id": {"in": doc_ids}})
        return {
            "tag": tag.name,
            "documents": [
                {"id": d.id, "title": d.title, "source_format": d.sourceFormat}
                for d in docs
            ],
        }
    finally:
        await db.disconnect()
