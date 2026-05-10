"""Deterministic handler for generate-pptx-blocks (Phase 10C)."""
from __future__ import annotations

import json
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import litellm
from prisma import Prisma

from officeplane.content_agent.renderers.blocks import parse_blocks_document
from officeplane.content_agent.renderers.pptx_blocks import render_pptx

log = logging.getLogger("officeplane.skills.generate-pptx-blocks")


PROMPT_TEMPLATE = """You are a deck-design assistant producing a PowerPoint presentation for OfficePlane.

Your job: read the source documents below and emit STRICT JSON with this schema:

{{
  "schema_version": "1.0",
  "title": "<deck title>",
  "modules": [
    {{
      "id": "module-<n>",
      "title": "<section name>",
      "lessons": [
        {{
          "id": "lesson-<uuid>",
          "title": "<slide-group heading>",
          "order": 0,
          "blocks": [
            {{"type": "title", "content": "<slide title>", "order": 0, "source_references": [...]}},
            {{"type": "text",  "content": "<bullet point>",  "order": 1, "source_references": [...]}},
            {{"type": "table", "content": "<JSON of {{headers, rows}}>", "order": 2, "source_references": [...]}}
          ]
        }}
      ]
    }}
  ]
}}

Slide model:
- Each `title` block within a lesson starts a NEW content slide.
- `text` blocks are bullet points on the current slide. Keep them ≤ 60 characters when possible.
- `table` blocks render as PowerPoint tables on the current slide.

Each `source_references` entry MUST include `document_id` and `document_title`.
Add `chapter_title`/`section_title`/`page_numbers` whenever you can pinpoint them.

Target slide count: {target_slides}

Brief:
{brief}

Source documents:
{source_blob}

Respond with the JSON object only. No prose, no markdown fences, no commentary.
"""


def _target_slide_hint(target: int | None) -> int:
    try:
        v = int(target) if target is not None else 12
    except (TypeError, ValueError):
        v = 12
    return max(3, min(40, v))


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


async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    source_ids = list(inputs.get("source_document_ids") or [])
    brief = str(inputs.get("brief") or "").strip()
    target_slides = _target_slide_hint(inputs.get("target_slide_count"))

    if not source_ids:
        raise ValueError("source_document_ids is required and must be non-empty")
    if not brief:
        raise ValueError("brief is required")

    sources = await _load_sources(source_ids)
    if not sources:
        raise ValueError(f"none of the provided source_document_ids resolved: {source_ids}")

    source_blob = _format_source_blob(sources)
    prompt = PROMPT_TEMPLATE.format(
        target_slides=target_slides,
        brief=brief,
        source_blob=source_blob,
    )

    model = os.getenv("OFFICEPLANE_AGENT_MODEL_FLASH", "deepseek/deepseek-v4-flash")
    log.info("generate-pptx-blocks via %s for sources=%s", model, source_ids)
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

    blocks_doc = parse_blocks_document(data)
    pptx_bytes = render_pptx(blocks_doc)

    job_id = str(uuid.uuid4())
    workspace = Path(os.getenv("CONTENT_AGENT_WORKSPACE", "/data/workspaces")) / job_id
    workspace.mkdir(parents=True, exist_ok=True)
    out_path = workspace / "output.pptx"
    out_path.write_bytes(pptx_bytes)

    blocks_count = sum(
        len(l.blocks) for m in blocks_doc.modules for l in m.lessons
    )

    return {
        "file_path": str(out_path),
        "file_url": f"/data/workspaces/{job_id}/output.pptx",
        "blocks_count": blocks_count,
        "source_document_ids": source_ids,
        "model": model,
        "title": blocks_doc.title,
    }
