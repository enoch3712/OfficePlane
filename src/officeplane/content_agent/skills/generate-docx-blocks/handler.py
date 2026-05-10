"""Deterministic handler for generate-docx-blocks (Phase 10B)."""
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
from officeplane.content_agent.renderers.docx_blocks import render_docx

log = logging.getLogger("officeplane.skills.generate-docx-blocks")


PROMPT_TEMPLATE = """You are a course content writer producing a Microsoft Word document for OfficePlane.

Your job: read the source documents below and emit a STRICT JSON object with this schema:

{{
  "schema_version": "1.0",
  "title": "<document title>",
  "modules": [
    {{
      "id": "module-<n>",
      "title": "<short>",
      "lessons": [
        {{
          "id": "lesson-<uuid>",
          "title": "<short>",
          "order": 0,
          "blocks": [
            {{"type": "title", "content": "<heading>", "order": 0, "source_references": [...]}},
            {{"type": "text",  "content": "<prose>",   "order": 1, "source_references": [...]}},
            {{"type": "table", "content": "<JSON string of {{headers, rows}}>", "order": 2, "source_references": [...]}}
          ]
        }}
      ]
    }}
  ]
}}

Each `source_references` entry MUST include `document_id` (one of the provided source IDs)
and the human-readable `document_title`. Add `chapter_title` / `section_title` /
`page_numbers` whenever you can pinpoint them from the source content.

Block-type rules:
- `title`: short heading text (≤ 80 chars)
- `text`: 1-4 sentence paragraph
- `table`: `content` is a JSON-encoded string of `{{"headers": [...], "rows": [[...], ...]}}`
- `image`: omit unless an actual image asset is provided

Target length: {target_length}

Brief:
{brief}

Source documents:
{source_blob}

Respond with the JSON object only. No prose, no markdown fences, no commentary.
"""


def _target_length_hint(value: str | None) -> str:
    v = (value or "medium").lower()
    if v == "short":
        return "Roughly 1 page (1 module, 1-2 lessons, 4-8 blocks total)."
    if v == "long":
        return "Roughly 10+ pages (3-5 modules, 3-5 lessons each, dense block coverage)."
    return "Roughly 3-5 pages (2-3 modules, 2-3 lessons each, balanced text + tables)."


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
    target_length = inputs.get("target_length")

    if not source_ids:
        raise ValueError("source_document_ids is required and must be non-empty")
    if not brief:
        raise ValueError("brief is required")

    sources = await _load_sources(source_ids)
    if not sources:
        raise ValueError(f"none of the provided source_document_ids resolved: {source_ids}")

    source_blob = _format_source_blob(sources)
    prompt = PROMPT_TEMPLATE.format(
        target_length=_target_length_hint(target_length),
        brief=brief,
        source_blob=source_blob,
    )

    model = os.getenv("OFFICEPLANE_AGENT_MODEL_FLASH", "deepseek/deepseek-v4-flash")
    log.info("generate-docx-blocks via %s for sources=%s", model, source_ids)
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
    docx_bytes = render_docx(blocks_doc)

    job_id = str(uuid.uuid4())
    workspace = Path(os.getenv("CONTENT_AGENT_WORKSPACE", "/data/workspaces")) / job_id
    workspace.mkdir(parents=True, exist_ok=True)
    out_path = workspace / "output.docx"
    out_path.write_bytes(docx_bytes)

    blocks_count = sum(
        len(l.blocks) for m in blocks_doc.modules for l in m.lessons
    )

    return {
        "file_path": str(out_path),
        "file_url": f"/data/workspaces/{job_id}/output.docx",
        "blocks_count": blocks_count,
        "source_document_ids": source_ids,
        "model": model,
        "title": blocks_doc.title,
    }
