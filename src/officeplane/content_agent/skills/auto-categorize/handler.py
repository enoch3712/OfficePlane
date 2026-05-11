"""auto-categorize — suggest which Collection a document belongs to."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import litellm
from prisma import Prisma

from officeplane.content_agent.persistence import persist_skill_invocation

log = logging.getLogger("officeplane.skills.auto-categorize")

SCORE_THRESHOLD = 0.55  # below this, propose a new collection


async def _get_document_signature(db: Prisma, document_id: str) -> dict[str, Any] | None:
    """Build the text signature for similarity matching."""
    doc = await db.document.find_unique(where={"id": document_id})
    if not doc:
        return None
    parts: list[str] = []
    if doc.title:
        parts.append(doc.title)
    if doc.summary:
        parts.append(doc.summary)
    if doc.topics:
        parts.append(" ".join(doc.topics))
    return {
        "id": doc.id,
        "title": doc.title,
        "summary": doc.summary or "",
        "topics": list(doc.topics or []),
        "text": " ".join(parts).lower(),
    }


async def _get_collection_signatures(db: Prisma) -> list[dict[str, Any]]:
    """Build text signatures for every collection (concat name+description+member summaries)."""
    collections = await db.collection.find_many()
    out = []
    for col in collections:
        members = await db.documentcollection.find_many(where={"collectionId": col.id})
        member_summaries: list[str] = []
        member_topics: list[str] = []
        for m in members:
            d = await db.document.find_unique(where={"id": m.documentId})
            if d:
                if d.summary:
                    member_summaries.append(d.summary)
                if d.topics:
                    member_topics.extend(d.topics)
        parts = [col.name, col.description or ""] + member_summaries[:5] + member_topics
        out.append({
            "id": col.id,
            "name": col.name,
            "description": col.description or "",
            "text": " ".join(p for p in parts if p).lower(),
            "member_count": len(members),
        })
    return out


def _jaccard(a: str, b: str) -> float:
    """Simple Jaccard similarity on whitespace-split word sets. Lowercased upstream."""
    sa = set(w for w in a.split() if len(w) > 3)
    sb = set(w for w in b.split() if len(w) > 3)
    if not sa or not sb:
        return 0.0
    inter = len(sa & sb)
    union = len(sa | sb)
    return inter / union if union else 0.0


async def _score_existing(target: dict[str, Any], collections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Score every collection against the target via Jaccard.
    (If Phase 14 vector search becomes available, callers can swap to embedding similarity.)"""
    scored = []
    for col in collections:
        score = _jaccard(target["text"], col["text"])
        scored.append({
            "collection_id": col["id"],
            "name": col["name"],
            "score": round(score, 4),
            "reason": _reason_string(target, col, score),
            "member_count": col["member_count"],
        })
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored


def _reason_string(target: dict[str, Any], col: dict[str, Any], score: float) -> str:
    common_topics = set(target.get("topics") or []) & set(
        w for w in (col["text"].split()) if len(w) > 3
    )
    if common_topics:
        return f"shares topics: {', '.join(sorted(common_topics))[:80]}"
    if score > 0.3:
        return f"word overlap {score:.2f} with collection summary"
    return f"low overlap (score {score:.2f})"


async def _propose_new_collection(target: dict[str, Any]) -> dict[str, Any]:
    """Ask DeepSeek to propose a Collection name + description for this orphan doc."""
    model = os.getenv("OFFICEPLANE_AGENT_MODEL_FLASH", "deepseek/deepseek-v4-flash")
    prompt = (
        "Propose a short Collection name (2-4 words) and a one-sentence description "
        "for grouping documents like this:\n\n"
        f"Title: {target['title']}\n"
        f"Summary: {target['summary']}\n"
        f"Topics: {', '.join(target.get('topics') or []) or '(none)'}\n\n"
        "Respond with ONLY a JSON object of shape "
        '{"name": "...", "description": "..."} — no prose, no markdown fences.'
    )
    try:
        resp = await litellm.acompletion(
            model=model,
            temperature=0.3,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        data = json.loads(resp.choices[0].message.content or "{}")
        return {
            "name": str(data.get("name") or "Uncategorized").strip()[:80],
            "description": str(data.get("description") or "").strip()[:200],
            "reason": "No existing collection scored above threshold",
        }
    except Exception as e:
        log.warning("new-collection proposal failed: %s", e)
        return {
            "name": "Uncategorized",
            "description": "",
            "reason": f"LLM proposal failed ({e}); using default",
        }


async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    t0 = time.time()
    document_id = str(inputs.get("document_id") or "").strip()
    if not document_id:
        raise ValueError("document_id is required")

    _raw_max = inputs.get("max_suggestions")
    max_suggestions = int(_raw_max) if _raw_max is not None else 3
    if max_suggestions < 1 or max_suggestions > 20:
        raise ValueError("max_suggestions must be 1..20")

    db = Prisma()
    await db.connect()
    try:
        target = await _get_document_signature(db, document_id)
        if not target:
            raise ValueError(f"document not found: {document_id}")

        collections = await _get_collection_signatures(db)
        scored = await _score_existing(target, collections)
        top = scored[:max_suggestions]
        best_score = top[0]["score"] if top else 0.0

        new_proposal: dict[str, Any] | None = None
        if best_score < SCORE_THRESHOLD:
            new_proposal = await _propose_new_collection(target)
    finally:
        await db.disconnect()

    model = os.getenv("OFFICEPLANE_AGENT_MODEL_FLASH", "deepseek/deepseek-v4-flash")
    result = {
        "document_id": document_id,
        "suggested_collections": top,
        "new_collection_proposal": new_proposal,
        "model": model,
    }

    try:
        await persist_skill_invocation(
            skill="auto-categorize",
            model=model,
            workspace_id=None,
            inputs=inputs,
            outputs={
                "document_id": document_id,
                "top_score": best_score,
                "suggestion_count": len(top),
                "new_proposal_name": (new_proposal or {}).get("name"),
            },
            status="ok",
            error_message=None,
            duration_ms=int((time.time() - t0) * 1000),
        )
    except Exception:
        pass

    return result
