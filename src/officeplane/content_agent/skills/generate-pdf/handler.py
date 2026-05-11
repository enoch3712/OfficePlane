"""Handler for the generate-pdf skill.

Generates a PDF document from ingested source documents using the agnostic
Document tree (CommonMark/Pandoc-aligned). The PDF is produced by first
rendering to DOCX via render_docx, then converting with libreoffice --headless
(already installed in the api Docker image — no extra pip deps).

Entry point: ``execute(*, inputs, **_)`` — consumed by SkillExecutor.
"""
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

from officeplane.content_agent.document_ops import walk_nodes
from officeplane.content_agent.persistence import (
    persist_derivations_from_document,
    persist_initial_revision,
    persist_skill_invocation,
)
from officeplane.content_agent.renderers.document import document_to_dict, parse_document
from officeplane.content_agent.renderers.pdf_render import render_pdf

log = logging.getLogger("officeplane.skills.generate-pdf")


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

PROMPT_TEMPLATE = """You are writing a PDF document for OfficePlane.

Output a STRICT JSON object conforming to this AGNOSTIC document schema
(aligned with CommonMark / Pandoc AST):

{{
  "type": "document",
  "schema_version": "1.0",
  "meta": {{"title": "<doc title>", "language": "en"}},
  "children": [
    {{
      "type": "section",
      "id": "<short-id>",
      "level": 1,
      "heading": "<section title>",
      "children": [
        {{"type": "heading", "level": 2, "text": "<sub-heading>"}},
        {{"type": "paragraph", "text": "<prose>"}},
        {{"type": "list", "ordered": false, "items": [
            {{"type": "paragraph", "text": "<bullet>"}}
        ]}},
        {{"type": "table", "headers": ["A","B"], "rows": [["1","2"]]}},
        {{"type": "callout", "variant": "note", "text": "<aside>"}},
        {{"type": "section", "level": 2, "heading": "<sub-section>", "children": [...]}}
      ]
    }}
  ],
  "attributions": [
    {{"node_id": "<id-of-some-node>", "document_id": "<source-doc-uuid>", "section_id": "<source-section-id>"}}
  ]
}}

Rules:
- Sections nest recursively. Use `level` 1..6 to indicate depth.
- Block types: heading, paragraph, list, table, figure, code, callout, quote, divider.
- NEVER emit "modules" or "lessons" — use nested sections instead.
- Every non-trivial node SHOULD have an `id` (short string). attributions reference these ids.
- Provide at least one attribution per major section pointing back to a source document_id.

Audience: {audience}
Style: {style}
Target length: {length_hint}

Brief:
{brief}

Source documents:
{source_blob}

Respond with the JSON object only — no prose, no markdown fences.
"""


# ---------------------------------------------------------------------------
# Length hint mapping
# ---------------------------------------------------------------------------

def _length_hint(value: str | None) -> str:
    v = (value or "medium").lower()
    if v == "short":
        return "≈1 page, 2-3 sections, ~10 nodes total"
    if v == "long":
        return "≈10+ pages, 5+ sections with sub-sections, ~80+ nodes total"
    return "≈3-5 pages, 3-5 sections (some with sub-sections), ~30 nodes total"


# ---------------------------------------------------------------------------
# Source loading helpers
# ---------------------------------------------------------------------------

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
                        {
                            "section_id": str(s.id),
                            "title": s.title,
                            "summary": s.summary,
                        }
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


def _format_source_blob(sources: list[dict[str, Any]]) -> str:
    parts = []
    for s in sources:
        topics = ", ".join(s.get("topics", []) or [])
        parts.append(
            f"### {s['title']} ({s['document_id']})\n"
            + (f"Topics: {topics}\n" if topics else "")
            + (f"Summary: {s['summary']}\n" if s.get("summary") else "")
        )
        for chap in s.get("chapters", []):
            parts.append(f"  Chapter: {chap['title']} ({chap['chapter_id']})")
            if chap.get("summary"):
                parts.append(f"    Summary: {chap['summary']}")
            for sec in chap.get("sections", []):
                parts.append(f"    Section: {sec['title']} ({sec['section_id']})")
                if sec.get("summary"):
                    parts.append(f"      Summary: {sec['summary']}")
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    """Generate a .pdf from source documents using the agnostic Document tree.

    Args:
        inputs: Skill inputs dict — see SKILL.md for the full schema.

    Returns:
        Dict with file_path, file_url, title, node_count, model,
        source_document_ids.

    Raises:
        ValueError: on invalid inputs or non-JSON LLM response.
        RuntimeError: if libreoffice conversion fails.
    """
    t0 = time.time()
    try:
        source_ids: list[str] = list(inputs.get("source_document_ids") or [])
        brief: str = str(inputs.get("brief") or "").strip()
        style: str = str(inputs.get("style") or "professional").strip()
        audience: str = str(inputs.get("audience") or "general audience").strip()
        target_length: str | None = inputs.get("target_length")

        # --- validation ---
        if not source_ids:
            raise ValueError("source_document_ids is required and must be non-empty")
        if not brief:
            raise ValueError("brief is required")

        # --- load sources ---
        sources = await _load_sources(source_ids)
        if not sources:
            raise ValueError(
                f"none of the provided source_document_ids resolved: {source_ids}"
            )

        source_blob = _format_source_blob(sources)
        prompt = PROMPT_TEMPLATE.format(
            audience=audience,
            style=style,
            length_hint=_length_hint(target_length),
            brief=brief,
            source_blob=source_blob,
        )

        model = os.getenv("OFFICEPLANE_AGENT_MODEL_FLASH", "deepseek/deepseek-v4-flash")
        log.info("generate-pdf via %s for sources=%s", model, source_ids)

        response = await litellm.acompletion(
            model=model,
            temperature=0.2,
            response_format={"type": "json_object"},
            messages=[{"role": "user", "content": prompt}],
        )
        raw: str = response.choices[0].message.content or "{}"

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM did not return JSON: {exc}") from exc

        doc = parse_document(data)

        job_id = str(uuid.uuid4())
        workspace_root = Path(os.getenv("CONTENT_AGENT_WORKSPACE", "/data/workspaces"))
        workspace = workspace_root / job_id
        workspace.mkdir(parents=True, exist_ok=True)

        pdf_bytes = render_pdf(doc, workspace_dir=workspace)

        out_path = workspace / "output.pdf"
        out_path.write_bytes(pdf_bytes)

        node_count = sum(1 for _ in walk_nodes(doc))

        result_dict = {
            "file_path": str(out_path),
            "file_url": f"/data/workspaces/{job_id}/output.pdf",
            "title": doc.meta.title,
            "node_count": node_count,
            "model": model,
            "source_document_ids": source_ids,
        }

        # Snapshot the Document JSON for future edits
        (workspace / "document.json").write_text(json.dumps(document_to_dict(doc)))

        # Persist provenance + initial revision
        await persist_initial_revision(
            workspace_id=job_id,
            op="create",
            payload={"skill": "generate-pdf", "title": doc.meta.title, "node_count": node_count},
            snapshot_path=str(workspace / "document.json"),
        )
        await persist_derivations_from_document(
            workspace_id=job_id,
            generated_doc_path=str(out_path),
            doc=doc,
            skill="generate-pdf",
            model=model,
            prompt=prompt,
        )
        await persist_skill_invocation(
            skill="generate-pdf",
            model=model,
            workspace_id=job_id,
            inputs=inputs,
            outputs=result_dict,
            status="ok",
            error_message=None,
            duration_ms=int((time.time() - t0) * 1000),
        )
        return result_dict

    except Exception as e:
        await persist_skill_invocation(
            skill="generate-pdf",
            model=None,
            workspace_id=None,
            inputs=inputs,
            outputs={},
            status="error",
            error_message=str(e),
            duration_ms=int((time.time() - t0) * 1000),
        )
        raise
