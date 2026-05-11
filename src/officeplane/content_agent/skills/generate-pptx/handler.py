"""Handler for the generate-pptx skill.

Generates a PowerPoint deck from ingested source documents using the agnostic
Document tree (CommonMark/Pandoc-aligned), parametrised by slide_count, style,
audience, and tone.

Entry point: ``execute(*, inputs, **_)`` — consumed by SkillExecutor.
"""
from __future__ import annotations

import io
import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

import litellm
from pptx import Presentation
from prisma import Prisma

from officeplane.content_agent.persistence import (
    persist_derivations_from_document,
    persist_initial_revision,
    persist_skill_invocation,
)
from officeplane.content_agent.renderers.document import document_to_dict, parse_document
from officeplane.content_agent.renderers.pptx_render import render_pptx

log = logging.getLogger("officeplane.skills.generate-pptx")


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

PROMPT_TEMPLATE = """You are designing a PowerPoint deck for OfficePlane.

Output a STRICT JSON object conforming to this AGNOSTIC document schema
(CommonMark / Pandoc-aligned). Sections nest recursively. Block types:
heading, paragraph, list, table, figure, code, callout, quote, divider.

The agnostic schema:
{{
  "type": "document",
  "schema_version": "1.0",
  "meta": {{
    "title": "<deck title>",
    "language": "en",
    "render_hints": {{"max_slides": {slide_count}}}
  }},
  "children": [
    {{"type": "section", "id": "<id>", "level": 1, "heading": "<section>", "children": [
      {{"type": "paragraph", "text": "<short bullet body>"}},
      {{"type": "list", "ordered": false, "items": [{{"type": "paragraph", "text": "<bullet>"}}]}},
      {{"type": "section", "level": 2, "heading": "<sub-slide>", "children": [...]}}
    ]}}
  ],
  "attributions": [
    {{"node_id": "<id>", "document_id": "<source-uuid>", "section_id": "<source-section-id>"}}
  ]
}}

Layout intent — each LEAF-BEARING section becomes one slide. Level-1 sections with
sub-sections produce a section-divider slide. So plan the section tree to hit
~{slide_count} slides total (counting title slide + section dividers + content slides).

CRITICAL constraints:
- Audience: {audience}
- Style: {style}
- Tone: {tone}
- Target slide count: {slide_count} (the renderer will hard-truncate if exceeded)
- NEVER emit "modules" or "lessons" — use nested sections.
- Each content slide should have ≤ 6 bullet items.
- Headings ≤ 60 chars. Bullets ≤ 18 words.
- Provide at least one attribution per major section pointing back to a source document_id.

Brief:
{brief}

Source documents:
{source_blob}

Respond with the JSON object only — no prose, no markdown fences.
"""


# ---------------------------------------------------------------------------
# Source loading helpers (self-contained — not imported from generate-docx)
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
    """Generate a .pptx from source documents using the agnostic Document tree.

    Args:
        inputs: Skill inputs dict — see SKILL.md for the full schema.

    Returns:
        Dict with file_path, file_url, title, slide_count, model,
        source_document_ids.

    Raises:
        ValueError: on invalid inputs or non-JSON LLM response.
    """
    t0 = time.time()
    try:
        source_ids: list[str] = list(inputs.get("source_document_ids") or [])
        brief: str = str(inputs.get("brief") or "").strip()
        _slide_count_raw = inputs.get("slide_count")
        slide_count: int = int(_slide_count_raw) if _slide_count_raw is not None else 10
        style: str = str(inputs.get("style") or "professional").strip()
        audience: str = str(inputs.get("audience") or "general").strip()
        tone: str = str(inputs.get("tone") or "neutral").strip()

        # --- validation (all checks before any I/O) ---
        if not source_ids:
            raise ValueError("source_document_ids is required and must be non-empty")
        if not brief:
            raise ValueError("brief is required")
        if slide_count < 1 or slide_count > 100:
            raise ValueError("slide_count must be 1..100")

        # --- load sources ---
        sources = await _load_sources(source_ids)
        if not sources:
            raise ValueError(
                f"none of the provided source_document_ids resolved: {source_ids}"
            )

        source_blob = _format_source_blob(sources)
        prompt = PROMPT_TEMPLATE.format(
            slide_count=slide_count,
            style=style,
            audience=audience,
            tone=tone,
            brief=brief,
            source_blob=source_blob,
        )

        model = os.getenv("OFFICEPLANE_AGENT_MODEL_FLASH", "deepseek/deepseek-v4-flash")
        log.info("generate-pptx via %s for sources=%s slide_count=%d", model, source_ids, slide_count)

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

        # Force-set the slide cap (LLM may have ignored or set differently)
        doc.meta.render_hints["max_slides"] = slide_count

        job_id = str(uuid.uuid4())
        workspace_root = Path(os.getenv("CONTENT_AGENT_WORKSPACE", "/data/workspaces"))
        workspace = workspace_root / job_id
        workspace.mkdir(parents=True, exist_ok=True)

        pptx_bytes = render_pptx(doc, workspace_dir=workspace)

        # Count actual slides in the rendered output
        pres = Presentation(io.BytesIO(pptx_bytes))
        actual_slides = len(pres.slides)

        out_path = workspace / "output.pptx"
        out_path.write_bytes(pptx_bytes)

        result_dict = {
            "file_path": str(out_path),
            "file_url": f"/data/workspaces/{job_id}/output.pptx",
            "title": doc.meta.title or "Untitled",
            "slide_count": actual_slides,
            "model": model,
            "source_document_ids": source_ids,
        }

        # Snapshot the Document JSON for future edits
        (workspace / "document.json").write_text(json.dumps(document_to_dict(doc)))

        # Persist provenance + initial revision
        await persist_initial_revision(
            workspace_id=job_id,
            op="create",
            payload={"skill": "generate-pptx", "title": doc.meta.title or "Untitled", "slide_count": actual_slides},
            snapshot_path=str(workspace / "document.json"),
        )
        await persist_derivations_from_document(
            workspace_id=job_id,
            generated_doc_path=str(out_path),
            doc=doc,
            skill="generate-pptx",
            model=model,
            prompt=prompt,
        )
        await persist_skill_invocation(
            skill="generate-pptx",
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
            skill="generate-pptx",
            model=None,
            workspace_id=None,
            inputs=inputs,
            outputs={},
            status="error",
            error_message=str(e),
            duration_ms=int((time.time() - t0) * 1000),
        )
        raise
