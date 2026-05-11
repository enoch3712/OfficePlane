"""Grounded chat endpoint — retrieval-augmented Q&A.

Flow:
  1. Caller posts query + scope (document_ids or collection_id, optional).
  2. We call POST http://localhost:8001/api/search/semantic to retrieve passages.
  3. If retrieval succeeds → prompt DeepSeek with passages as context, ask for an
     answer that cites passage indices [1], [2], ...
  4. Map indices back to source metadata; return answer + citations.
  5. If retrieval fails → answer ungrounded with a flag.
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

import httpx
import litellm
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from officeplane.content_agent.persistence import persist_skill_invocation

log = logging.getLogger("officeplane.api.chat")
router = APIRouter(prefix="/api/chat", tags=["chat"])


API_BASE = os.getenv("OFFICEPLANE_INTERNAL_API_URL", "http://localhost:8001")
TOP_K = 6


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class GroundedChatRequest(BaseModel):
    query: str
    document_ids: list[str] | None = None
    collection_id: str | None = None
    history: list[ChatMessage] = Field(default_factory=list)
    top_k: int = Field(default=TOP_K, ge=1, le=20)


class Citation(BaseModel):
    index: int
    chunk_id: str
    document_id: str
    text_excerpt: str
    score: float


class GroundedChatResponse(BaseModel):
    answer: str
    citations: list[Citation]
    mode: str  # "grounded" | "ungrounded"
    model: str
    retrieval_count: int


@router.post("/grounded", response_model=GroundedChatResponse)
async def grounded_chat(req: GroundedChatRequest):
    t0 = time.time()
    query = req.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="query is required")

    passages = await _retrieve(req.query, req.document_ids, req.collection_id, req.top_k)
    model = os.getenv("OFFICEPLANE_AGENT_MODEL_FLASH", "deepseek/deepseek-v4-flash")

    if not passages:
        # Ungrounded fallback — still answer, but flag it
        answer = await _llm_answer_ungrounded(req, model)
        result = GroundedChatResponse(
            answer=answer, citations=[], mode="ungrounded",
            model=model, retrieval_count=0,
        )
    else:
        answer = await _llm_answer_grounded(req, passages, model)
        citations = [
            Citation(
                index=i + 1,
                chunk_id=str(p["chunk_id"]),
                document_id=str(p["document_id"]),
                text_excerpt=p["content"][:280],
                score=float(p.get("score") or 0.0),
            )
            for i, p in enumerate(passages)
        ]
        result = GroundedChatResponse(
            answer=answer, citations=citations, mode="grounded",
            model=model, retrieval_count=len(passages),
        )

    try:
        await persist_skill_invocation(
            skill="grounded-chat", model=model, workspace_id=None,
            inputs={"query": query[:200], "scope_docs": req.document_ids or [],
                    "scope_collection": req.collection_id, "top_k": req.top_k},
            outputs={"mode": result.mode, "retrieval_count": result.retrieval_count,
                     "answer_length": len(answer)},
            status="ok", error_message=None,
            duration_ms=int((time.time() - t0) * 1000),
        )
    except Exception:
        pass

    return result


async def _retrieve(
    query: str,
    document_ids: list[str] | None,
    collection_id: str | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Call /api/search/semantic. Return [] on any failure (network, 4xx, 5xx)."""
    payload: dict[str, Any] = {"query": query, "limit": limit}
    if document_ids:
        payload["document_ids"] = document_ids
    elif collection_id:
        payload["collection_id"] = collection_id

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(f"{API_BASE}/api/search/semantic", json=payload)
        if r.status_code != 200:
            log.info("retrieval skipped: search endpoint returned %s", r.status_code)
            return []
        j = r.json()
        return j.get("results") or []
    except Exception as e:
        log.info("retrieval skipped: %s", e)
        return []


async def _llm_answer_grounded(
    req: GroundedChatRequest, passages: list[dict[str, Any]], model: str,
) -> str:
    context_blocks = []
    for i, p in enumerate(passages):
        context_blocks.append(f"[{i+1}] ({p['document_id']}): {p['content']}")
    context = "\n\n".join(context_blocks)

    history_str = ""
    if req.history:
        for m in req.history[-8:]:
            history_str += f"\n{m.role.upper()}: {m.content}"

    prompt = (
        "You are a careful research assistant. Answer the user's question using ONLY the "
        "PASSAGES below. If the passages don't contain the answer, say so. Cite by passage "
        "index in square brackets, e.g. [1], [2]. Multiple citations OK: [1][3].\n\n"
        f"PASSAGES:\n{context}\n\n"
        f"PRIOR CONVERSATION:{history_str}\n\n"
        f"USER QUESTION: {req.query}\n\n"
        "ANSWER (with citations):"
    )

    resp = await litellm.acompletion(
        model=model,
        temperature=0.1,
        messages=[{"role": "user", "content": prompt}],
    )
    return (resp.choices[0].message.content or "").strip()


async def _llm_answer_ungrounded(req: GroundedChatRequest, model: str) -> str:
    history_str = ""
    if req.history:
        for m in req.history[-8:]:
            history_str += f"\n{m.role.upper()}: {m.content}"
    prompt = (
        "You're a helpful assistant. The user has asked a question, but we couldn't "
        "retrieve any grounding passages from their documents. Answer using general "
        "knowledge, but clearly state that this answer is NOT grounded in their documents. "
        f"\n\nPRIOR CONVERSATION:{history_str}\n\nUSER: {req.query}\n\nASSISTANT:"
    )
    resp = await litellm.acompletion(
        model=model, temperature=0.2,
        messages=[{"role": "user", "content": prompt}],
    )
    return (resp.choices[0].message.content or "").strip()
