"""GET /api/documents/{id}/lineage — provenance + revision graph for a document."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from prisma import Prisma

log = logging.getLogger("officeplane.api.lineage")

router = APIRouter(tags=["lineage"])


@router.get("/api/documents/{document_id}/lineage")
async def get_document_lineage(
    document_id: str,
    workspace_id: str | None = Query(None),
):
    db = Prisma()
    await db.connect()
    try:
        # 1. Confirm source document exists
        src_doc = await db.document.find_unique(
            where={"id": document_id},
            include={"chapters": {"include": {"sections": True}}},
        )
        if not src_doc:
            raise HTTPException(status_code=404, detail="document not found")

        # 2. Find target workspace
        if workspace_id is None:
            # Most recent workspace whose derivations reference this source doc
            recent_derivation = await db.derivation.find_first(
                where={"sourceDocumentId": document_id},
                order={"createdAt": "desc"},
            )
            workspace_id = recent_derivation.workspaceId if recent_derivation else None

        if workspace_id is None:
            # No derivations yet — return shell
            return _empty_response(src_doc, workspace_id="")

        # 3. Pull all derivations, revisions for that workspace
        derivations = await db.derivation.find_many(
            where={"workspaceId": workspace_id},
            order={"createdAt": "asc"},
        )
        revisions = await db.documentrevision.find_many(
            where={"workspaceId": workspace_id},
            order={"revisionNumber": "asc"},
        )

        # 4. Read the generated document.json (if it exists) to build the node list
        nodes = []
        output_path = ""
        workspace_dir = Path("/data/workspaces") / workspace_id
        doc_json_path = workspace_dir / "document.json"
        if doc_json_path.exists():
            try:
                doc_data = json.loads(doc_json_path.read_text())
                nodes = _flatten_nodes(doc_data)
            except Exception as e:
                log.warning("failed to load %s: %s", doc_json_path, e)

        # Pick an output_path — prefer derivation.generatedDocPath, else workspace/output.docx
        if derivations:
            output_path = derivations[0].generatedDocPath or ""
        if not output_path:
            for ext in ("docx", "pptx"):
                cand = workspace_dir / f"output.{ext}"
                if cand.exists():
                    output_path = str(cand)
                    break

        # 5. Build response
        return {
            "document": {
                "id": src_doc.id,
                "title": src_doc.title,
                "workspace_id": workspace_id,
                "output_path": output_path,
            },
            "nodes": nodes,
            "sources": [_source_to_dict(src_doc)],
            "derivations": [_derivation_to_dict(d) for d in derivations],
            "revisions": [_revision_to_dict(r) for r in revisions],
        }
    finally:
        await db.disconnect()


def _empty_response(src_doc, *, workspace_id: str) -> dict[str, Any]:
    return {
        "document": {"id": src_doc.id, "title": src_doc.title,
                     "workspace_id": workspace_id, "output_path": ""},
        "nodes": [],
        "sources": [_source_to_dict(src_doc)],
        "derivations": [],
        "revisions": [],
    }


def _source_to_dict(src_doc) -> dict[str, Any]:
    chapters = []
    for ch in (src_doc.chapters or []):
        chapters.append({
            "id": ch.id,
            "title": ch.title,
            "sections": [{"id": s.id, "title": s.title} for s in (ch.sections or [])],
        })
    return {"id": src_doc.id, "title": src_doc.title, "chapters": chapters}


def _derivation_to_dict(d) -> dict[str, Any]:
    return {
        "id": d.id,
        "generated_node_id": d.generatedNodeId,
        "source_document_id": d.sourceDocumentId,
        "source_chapter_id": d.sourceChapterId,
        "source_section_id": d.sourceSectionId,
        "page_numbers": list(d.pageNumbers or []),
        "text_excerpt": d.textExcerpt,
        "skill": d.skill,
        "model": d.model,
        "confidence": d.confidence,
        "created_at": d.createdAt.isoformat() if d.createdAt else None,
    }


def _revision_to_dict(r) -> dict[str, Any]:
    payload = r.payload
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except json.JSONDecodeError:
            payload = {"_raw": payload}
    return {
        "id": r.id,
        "parent_revision_id": r.parentRevisionId,
        "revision_number": r.revisionNumber,
        "op": r.op,
        "payload": payload or {},
        "actor": r.actor,
        "created_at": r.createdAt.isoformat() if r.createdAt else None,
    }


def _flatten_nodes(doc_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten the agnostic Document tree into the UI node list."""
    out = []

    def _label(node: dict) -> str:
        t = node.get("type")
        if t == "section":
            return node.get("heading", "") or "(section)"
        if t == "heading":
            return node.get("text", "")
        if t in ("paragraph", "callout", "quote", "code"):
            text = node.get("text", "")
            return text[:80]
        if t == "list":
            return f"list ({len(node.get('items') or [])} items)"
        if t == "table":
            return f"table ({len(node.get('rows') or [])}×{len(node.get('headers') or [])})"
        if t == "figure":
            return node.get("caption") or node.get("prompt", "") or "(figure)"
        return t or "(node)"

    def _walk(node: dict, parent_id: str | None):
        node_id = node.get("id") or ""
        if not node_id:
            return
        out.append({
            "id": node_id,
            "type": node.get("type", ""),
            "label": _label(node),
            "parent_id": parent_id,
        })
        # Recurse for sections + lists
        if node.get("type") == "section":
            for c in node.get("children") or []:
                _walk(c, node_id)

    for top in doc_data.get("children") or []:
        _walk(top, None)
    return out
