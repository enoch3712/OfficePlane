"""generate-from-collection — multi-source Document generation."""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

import litellm
from prisma import Prisma

from officeplane.content_agent.renderers.document import (
    parse_document,
    document_to_dict,
)
from officeplane.content_agent.renderers.docx_render import render_docx
from officeplane.content_agent.renderers.pptx_render import render_pptx
from officeplane.content_agent.document_ops import walk_nodes
from officeplane.content_agent.persistence import (
    persist_skill_invocation,
    persist_derivations_from_document,
    persist_initial_revision,
)

log = logging.getLogger("officeplane.skills.generate-from-collection")


PROMPT = """You are producing a Microsoft Word document (or PowerPoint deck) for OfficePlane,
grounded in MULTIPLE source documents from a collection.

Output a STRICT JSON object conforming to the agnostic Document schema (CommonMark/Pandoc):

{{
  "type": "document",
  "schema_version": "1.0",
  "meta": {{"title": "<title>", "language": "en", "render_hints": {{"max_slides": {slide_cap_hint}}}}},
  "children": [
    {{"type": "section", "id": "<id>", "level": 1, "heading": "...", "children": [
      {{"type": "paragraph", "id": "<id>", "text": "..."}}
    ]}}
  ],
  "attributions": [
    {{"node_id": "<id>", "document_id": "<source-uuid>", "section_id": "<source-section-uuid>", "page_numbers": [n]}}
  ]
}}

CRITICAL: each major section MUST include attributions for the source it draws from.
A combined document is typically synthesised from multiple sources — explicitly attribute
each section to whichever input it grounds on. Some sections may attribute to multiple sources.

NEVER emit "modules" or "lessons" — recursive sections only.

Format: {format}
Audience: {audience}
Style: {style}
Tone: {tone}

Brief:
{brief}

Source documents ({n_sources}):
{source_blob}

Respond with the JSON object only.
"""


async def _load_sources(document_ids: list[str]) -> list[dict[str, Any]]:
    db = Prisma()
    await db.connect()
    try:
        sources = []
        for doc_id in document_ids:
            doc = await db.document.find_unique(where={"id": doc_id})
            if not doc:
                continue
            chapters = await db.chapter.find_many(
                where={"documentId": doc.id}, order={"orderIndex": "asc"}
            )
            chapter_blobs = []
            for chap in chapters:
                sections = await db.section.find_many(
                    where={"chapterId": chap.id}, order={"orderIndex": "asc"}
                )
                chapter_blobs.append({
                    "chapter_id": str(chap.id),
                    "title": chap.title,
                    "summary": chap.summary,
                    "sections": [
                        {"section_id": str(s.id), "title": s.title, "summary": s.summary}
                        for s in sections
                    ],
                })
            sources.append({
                "document_id": str(doc.id),
                "title": doc.title,
                "summary": doc.summary,
                "topics": list(doc.topics or []),
                "chapters": chapter_blobs,
            })
        return sources
    finally:
        await db.disconnect()


async def _resolve_collection_documents(collection_id: str) -> list[str]:
    db = Prisma()
    await db.connect()
    try:
        rows = await db.documentcollection.find_many(
            where={"collectionId": collection_id},
        )
        return [r.documentId for r in rows]
    finally:
        await db.disconnect()


def _format_source_blob(sources: list[dict[str, Any]]) -> str:
    parts = []
    for s in sources:
        topics = ", ".join(s.get("topics") or [])
        parts.append(
            f"### {s['title']} ({s['document_id']})\n"
            + (f"Topics: {topics}\n" if topics else "")
            + (f"Summary: {s.get('summary') or ''}\n" if s.get("summary") else "")
        )
        for chap in s.get("chapters") or []:
            parts.append(f"  Chapter: {chap['title']} ({chap['chapter_id']})")
            for sec in chap.get("sections") or []:
                parts.append(f"    Section: {sec['title']} ({sec['section_id']})")
    return "\n".join(parts)


async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    t0 = time.time()
    collection_id = inputs.get("collection_id")
    explicit_ids = inputs.get("source_document_ids") or []
    brief = str(inputs.get("brief") or "").strip()
    fmt = str(inputs.get("format") or "docx").lower()
    style = str(inputs.get("style") or "professional")
    audience = str(inputs.get("audience") or "general")
    tone = str(inputs.get("tone") or "neutral")
    slide_count = int(inputs.get("slide_count") or 10)

    if fmt not in ("docx", "pptx"):
        raise ValueError(f"format must be 'docx' or 'pptx', got '{fmt}'")
    if not brief:
        raise ValueError("brief is required")
    if not collection_id and not explicit_ids:
        raise ValueError("either collection_id or source_document_ids is required")

    try:
        # Resolve source ids
        if collection_id:
            resolved = await _resolve_collection_documents(collection_id)
            if not resolved:
                raise ValueError(f"collection '{collection_id}' contains no documents")
            source_ids = resolved
        else:
            source_ids = list(explicit_ids)

        sources = await _load_sources(source_ids)
        if not sources:
            raise ValueError(f"none of the source_document_ids resolved: {source_ids}")

        prompt = PROMPT.format(
            slide_cap_hint=slide_count if fmt == "pptx" else 0,
            format=fmt,
            audience=audience,
            style=style,
            tone=tone,
            brief=brief,
            n_sources=len(sources),
            source_blob=_format_source_blob(sources),
        )

        from officeplane.content_agent.model import model_for_skill
        model = model_for_skill("generate-from-collection")
        log.info(
            "generate-from-collection via %s for %d sources (fmt=%s)",
            model,
            len(sources),
            fmt,
        )
        response = await litellm.acompletion(
            model=model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content or "{}"
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM did not return JSON: {exc}") from exc

        doc = parse_document(data)
        if fmt == "pptx":
            doc.meta.render_hints["max_slides"] = slide_count

        job_id = str(uuid.uuid4())
        workspace = Path(os.getenv("CONTENT_AGENT_WORKSPACE", "/data/workspaces")) / job_id
        workspace.mkdir(parents=True, exist_ok=True)

        if fmt == "docx":
            out_bytes = render_docx(doc, workspace_dir=workspace)
            out_path = workspace / "output.docx"
        else:
            out_bytes = render_pptx(doc, workspace_dir=workspace)
            out_path = workspace / "output.pptx"
        out_path.write_bytes(out_bytes)
        (workspace / "document.json").write_text(json.dumps(document_to_dict(doc)))

        # Compute final counts
        node_count = sum(1 for _ in walk_nodes(doc))
        actual_slides = 0
        if fmt == "pptx":
            import io

            from pptx import Presentation

            actual_slides = len(Presentation(io.BytesIO(out_bytes)).slides)

        result: dict[str, Any] = {
            "file_path": str(out_path),
            "file_url": f"/data/workspaces/{job_id}/{out_path.name}",
            "title": doc.meta.title or "Untitled",
            "model": model,
            "format": fmt,
            "source_document_count": len(sources),
            "source_document_ids": source_ids,
        }
        if fmt == "docx":
            result["node_count"] = node_count
        else:
            result["slide_count"] = actual_slides

        # Persistence
        try:
            await persist_initial_revision(
                workspace_id=job_id,
                op="create",
                payload={
                    "skill": "generate-from-collection",
                    "title": doc.meta.title,
                    "format": fmt,
                    "node_count": node_count,
                    "source_count": len(sources),
                },
                snapshot_path=str(workspace / "document.json"),
            )
            await persist_derivations_from_document(
                workspace_id=job_id,
                generated_doc_path=str(out_path),
                doc=doc,
                skill="generate-from-collection",
                model=model,
                prompt=prompt,
            )
        except Exception as e:
            log.warning("persistence failed: %s", e)

        try:
            await persist_skill_invocation(
                skill="generate-from-collection",
                model=model,
                workspace_id=job_id,
                inputs=inputs,
                outputs=result,
                status="ok",
                error_message=None,
                duration_ms=int((time.time() - t0) * 1000),
            )
        except Exception:
            pass

        return result

    except Exception as e:
        try:
            await persist_skill_invocation(
                skill="generate-from-collection",
                model=None,
                workspace_id=None,
                inputs=inputs,
                outputs={},
                status="error",
                error_message=str(e),
                duration_ms=int((time.time() - t0) * 1000),
            )
        except Exception:
            pass
        raise
