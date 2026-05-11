"""Semantic search across all (or scoped) chunks."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from prisma import Prisma
from pydantic import BaseModel

from officeplane.memory.embedding_provider import get_embedding_provider

router = APIRouter(prefix="/api/search", tags=["search"])
log = logging.getLogger("officeplane.api.search")


class SemanticSearchRequest(BaseModel):
    query: str
    document_ids: list[str] | None = None
    collection_id: str | None = None
    limit: int = 10


@router.post("/semantic")
async def semantic_search(req: SemanticSearchRequest):
    if not req.query.strip():
        raise HTTPException(status_code=400, detail="query is required")
    if req.limit < 1 or req.limit > 100:
        raise HTTPException(status_code=400, detail="limit must be 1..100")

    try:
        provider = get_embedding_provider()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"embedding provider unavailable: {e}")

    q_vec = await provider.embed_one(req.query)
    vec_str = "[" + ",".join(f"{x:.7f}" for x in q_vec) + "]"

    db = Prisma()
    await db.connect()
    try:
        sql_parts = [
            "SELECT id, document_id, text AS content,"
            " 1 - (embedding <=> $1::vector) AS score"
            " FROM chunks WHERE embedding IS NOT NULL"
        ]
        params: list = [vec_str]

        if req.document_ids:
            params.append(req.document_ids)
            sql_parts.append(f"AND document_id = ANY(${len(params)}::uuid[])")
        elif req.collection_id:
            params.append(req.collection_id)
            sql_parts.append(
                f"AND document_id IN ("
                f"  SELECT document_id FROM document_collections"
                f"  WHERE collection_id = ${len(params)}::uuid"
                f")"
            )

        sql_parts.append("ORDER BY embedding <=> $1::vector")
        params.append(req.limit)
        sql_parts.append(f"LIMIT ${len(params)}")
        sql = " ".join(sql_parts)

        rows = await db.query_raw(sql, *params)
        return {
            "query": req.query,
            "count": len(rows),
            "results": [
                {
                    "chunk_id": r["id"],
                    "document_id": r["document_id"],
                    "content": r["content"],
                    "score": float(r["score"]),
                }
                for r in rows
            ],
        }
    finally:
        await db.disconnect()
