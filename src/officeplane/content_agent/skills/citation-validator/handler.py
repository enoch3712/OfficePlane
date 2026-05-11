"""citation-validator — score each generated node's grounding in its cited source."""
from __future__ import annotations

import json
import logging
import math
import os
import time
from pathlib import Path
from typing import Any

from prisma import Prisma

from officeplane.content_agent.persistence import persist_skill_invocation
from officeplane.memory.embedding_provider import get_embedding_provider

log = logging.getLogger("officeplane.skills.citation-validator")

DEFAULT_THRESHOLD = 0.55


def _cosine(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return dot / (na * nb)


def _flatten_node_text(doc_data: dict[str, Any]) -> dict[str, str]:
    """Return {node_id: textual_summary} for every leaf-ish node in the document."""
    out: dict[str, str] = {}

    def text_of(node: dict[str, Any]) -> str:
        t = node.get("type")
        if t == "section":
            return node.get("heading") or ""
        if t in ("paragraph", "heading", "quote", "callout", "code"):
            return node.get("text") or ""
        if t == "list":
            items = node.get("items") or []
            return " · ".join((it.get("text") or "") for it in items if isinstance(it, dict))
        if t == "table":
            headers = node.get("headers") or []
            rows = node.get("rows") or []
            flat_rows = [" | ".join(map(str, r)) for r in rows[:5]]
            return " · ".join([" | ".join(map(str, headers))] + flat_rows)
        if t == "figure":
            return (node.get("caption") or node.get("prompt") or "")
        return ""

    def walk(node: dict[str, Any]):
        nid = node.get("id")
        if nid:
            txt = text_of(node)
            if txt:
                out[nid] = txt
        for c in (node.get("children") or []):
            walk(c)
        for it in (node.get("items") or []):
            walk(it)

    for top in (doc_data.get("children") or []):
        walk(top)
    return out


async def _get_source_excerpt(db: Prisma, attribution: dict[str, Any]) -> str:
    """Pull the actual source text for an attribution from the database."""
    section_id = attribution.get("section_id")
    chapter_id = attribution.get("chapter_id")
    document_id = attribution.get("document_id")
    parts: list[str] = []

    if section_id:
        sec = await db.section.find_unique(where={"id": section_id})
        if sec:
            if sec.title:
                parts.append(sec.title)
            if sec.summary:
                parts.append(sec.summary)
            # Pull the section's pages
            pages = await db.page.find_many(where={"sectionId": section_id})
            for pg in pages[:3]:
                if pg.content:
                    parts.append(pg.content[:500])

    if not parts and chapter_id:
        chap = await db.chapter.find_unique(where={"id": chapter_id})
        if chap:
            if chap.title:
                parts.append(chap.title)
            if chap.summary:
                parts.append(chap.summary)

    if not parts and document_id:
        doc = await db.document.find_unique(where={"id": document_id})
        if doc:
            if doc.title:
                parts.append(doc.title)
            if doc.summary:
                parts.append(doc.summary)

    return " ".join(parts)[:1000]


async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    t0 = time.time()
    workspace_id = str(inputs.get("workspace_id") or "").strip()
    threshold = float(inputs.get("similarity_threshold") or DEFAULT_THRESHOLD)
    if not workspace_id:
        raise ValueError("workspace_id is required")
    if not (0.0 <= threshold <= 1.0):
        raise ValueError("similarity_threshold must be in [0, 1]")

    workspace_root = Path(os.getenv("CONTENT_AGENT_WORKSPACE", "/data/workspaces"))
    doc_path = workspace_root / workspace_id / "document.json"
    if not doc_path.exists():
        raise FileNotFoundError(f"document.json not found at {doc_path}")

    doc_data = json.loads(doc_path.read_text())
    node_texts = _flatten_node_text(doc_data)
    attributions = doc_data.get("attributions") or []
    if not attributions:
        return {
            "workspace_id": workspace_id,
            "overall_confidence": 0.0,
            "validated_count": 0,
            "unsupported_count": 0,
            "per_node": [],
            "note": "no attributions to validate",
        }

    try:
        provider = get_embedding_provider()
    except Exception as e:
        raise RuntimeError(f"embedding provider unavailable: {e}") from e

    db = Prisma()
    await db.connect()
    per_node: list[dict[str, Any]] = []
    try:
        for attr in attributions:
            node_id = attr.get("node_id")
            generated_text = node_texts.get(node_id) or ""
            source_excerpt = await _get_source_excerpt(db, attr)
            similarity = 0.0
            supported = False
            if generated_text and source_excerpt:
                try:
                    [gen_vec, src_vec] = await provider.embed_batch([generated_text, source_excerpt])
                    similarity = _cosine(gen_vec, src_vec)
                    supported = similarity >= threshold
                except Exception as e:
                    log.warning("embedding failed for node %s: %s", node_id, e)
            per_node.append({
                "node_id": node_id,
                "source_document_id": attr.get("document_id"),
                "source_section_id": attr.get("section_id"),
                "similarity": round(similarity, 4),
                "supported": supported,
                "source_excerpt": source_excerpt[:280],
                "generated_excerpt": generated_text[:280],
            })
    finally:
        await db.disconnect()

    validated_count = len(per_node)
    unsupported_count = sum(1 for r in per_node if not r["supported"])
    overall = (
        sum(r["similarity"] for r in per_node) / validated_count if validated_count else 0.0
    )

    result = {
        "workspace_id": workspace_id,
        "overall_confidence": round(overall, 4),
        "validated_count": validated_count,
        "unsupported_count": unsupported_count,
        "per_node": per_node,
    }

    try:
        await persist_skill_invocation(
            skill="citation-validator", model="gemini/gemini-embedding-001",
            workspace_id=workspace_id,
            inputs={"workspace_id": workspace_id, "threshold": threshold},
            outputs={
                "overall_confidence": result["overall_confidence"],
                "validated_count": validated_count,
                "unsupported_count": unsupported_count,
            },
            status="ok", error_message=None,
            duration_ms=int((time.time() - t0) * 1000),
        )
    except Exception:
        pass

    return result
