"""vector-search skill — semantic retrieval over chunks."""
from __future__ import annotations

import time
from typing import Any

from prisma import Prisma

from officeplane.content_agent.persistence import persist_skill_invocation
from officeplane.memory.embedding_provider import get_embedding_provider


async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    t0 = time.time()
    query = str(inputs.get("query") or "").strip()
    if not query:
        raise ValueError("query is required")
    document_ids = inputs.get("document_ids") or None
    collection_id = inputs.get("collection_id") or None
    limit = int(inputs.get("limit") or 10)

    try:
        provider = get_embedding_provider()
        q_vec = await provider.embed_one(query)
    except Exception as e:
        raise RuntimeError(f"embedding failed: {e}") from e

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

        if document_ids:
            params.append(list(document_ids))
            sql_parts.append(f"AND document_id = ANY(${len(params)}::uuid[])")
        elif collection_id:
            params.append(collection_id)
            sql_parts.append(
                f"AND document_id IN ("
                f"  SELECT document_id FROM document_collections"
                f"  WHERE collection_id = ${len(params)}::uuid"
                f")"
            )

        sql_parts.append("ORDER BY embedding <=> $1::vector")
        params.append(limit)
        sql_parts.append(f"LIMIT ${len(params)}")
        sql = " ".join(sql_parts)

        rows = await db.query_raw(sql, *params)
        results = [
            {
                "chunk_id": r["id"],
                "document_id": r["document_id"],
                "content": r["content"],
                "score": float(r["score"]),
            }
            for r in rows
        ]
    finally:
        await db.disconnect()

    out = {"count": len(results), "results": results, "query": query}
    try:
        await persist_skill_invocation(
            skill="vector-search",
            model="gemini/embedding-001",
            workspace_id=None,
            inputs=inputs,
            outputs={"count": len(results)},
            status="ok",
            error_message=None,
            duration_ms=int((time.time() - t0) * 1000),
        )
    except Exception:
        pass
    return out
