"""extract-tabular-data — walk ingested doc pages, extract canonical tables."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import litellm
from prisma import Prisma

from officeplane.content_agent.persistence import persist_skill_invocation

log = logging.getLogger("officeplane.skills.extract-tabular-data")


PROMPT = """You are extracting tabular data from an ingested document for downstream
structured consumers (e.g. Excel population).

Read each PAGE below and identify every table or structured numeric data block.
Return STRICT JSON.

Rules:
- DO NOT invent rows. Only include data that's literally in the source.
- Coerce obvious numbers from strings (e.g. "1,200" → 1200, "12.5%" → 0.125).
- If a column is a date, keep as ISO-8601 string ("YYYY-MM-DD") when possible.
- Infer column headers from context if a table has no explicit header row.
- Skip tables with fewer than 2 data rows unless they're clearly a summary.
- For each table provide a SHORT name (≤ 60 chars) that distils its purpose.
- Cap output at {max_tables} tables.

{hint_block}

WORKBOOK title: {title}

PAGES:
{pages_blob}

Respond with ONLY a JSON object of this shape:
{{
  "tables": [
    {{
      "name": "<short name>",
      "headers": ["col1", "col2", ...],
      "rows": [[val1, val2, ...], ...],
      "source_page": <int or null>,
      "source_section_id": "<section uuid or null>",
      "row_count": <int>,
      "column_types": ["text" | "number" | "date" | "percent" | null]
    }}
  ]
}}
"""


def _hint_block(hint: str | None) -> str:
    if not hint:
        return ""
    return f"\nFOCUS: {hint}\n"


async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    t0 = time.time()
    document_id = str(inputs.get("document_id") or "").strip()
    _raw_max = inputs.get("max_tables")
    max_tables = int(_raw_max) if _raw_max is not None else 20
    hint = inputs.get("hint")
    if not document_id:
        raise ValueError("document_id is required")
    if max_tables < 1 or max_tables > 100:
        raise ValueError("max_tables must be 1..100")

    db = Prisma()
    await db.connect()
    try:
        doc = await db.document.find_unique(where={"id": document_id})
        if not doc:
            raise ValueError(f"document not found: {document_id}")

        # Pull pages — try the chapter/section/page hierarchy first, fall back to flat pages
        page_records: list[dict[str, Any]] = []
        chapters = await db.chapter.find_many(
            where={"documentId": doc.id}, order={"orderIndex": "asc"}
        )
        for chap in chapters:
            sections = await db.section.find_many(
                where={"chapterId": chap.id}, order={"orderIndex": "asc"}
            )
            for sec in sections:
                pgs = await db.page.find_many(
                    where={"sectionId": sec.id}, order={"pageNumber": "asc"}
                )
                for p in pgs:
                    if p.content:
                        page_records.append({
                            "page_number": p.pageNumber,
                            "content": p.content[:6000],
                            "section_id": sec.id,
                            "section_title": sec.title,
                        })
        if not page_records:
            # Fallback: flat pages under the document
            pgs = await db.page.find_many(where={"documentId": doc.id}, order={"pageNumber": "asc"})
            for p in pgs:
                if p.content:
                    page_records.append({
                        "page_number": p.pageNumber,
                        "content": p.content[:6000],
                        "section_id": None,
                        "section_title": None,
                    })
    finally:
        await db.disconnect()

    if not page_records:
        return {
            "document_id": document_id, "title": doc.title,
            "table_count": 0, "tables": [], "model": "skipped",
            "note": "no page content available",
        }

    pages_blob_parts = []
    for pr in page_records:
        header = f"--- Page {pr['page_number']}"
        if pr.get("section_title"):
            header += f" · section: {pr['section_title']}"
        pages_blob_parts.append(header)
        pages_blob_parts.append(pr["content"])
        pages_blob_parts.append("")
    pages_blob = "\n".join(pages_blob_parts)

    prompt = PROMPT.format(
        max_tables=max_tables,
        hint_block=_hint_block(hint),
        title=doc.title,
        pages_blob=pages_blob,
    )
    model = os.getenv("OFFICEPLANE_AGENT_MODEL_FLASH", "deepseek/deepseek-v4-flash")

    resp = await litellm.acompletion(
        model=model,
        temperature=0.0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    raw = (resp.choices[0].message.content or "{}").strip()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM did not return valid JSON: {e}") from e

    tables_raw = data.get("tables") or []
    if not isinstance(tables_raw, list):
        tables_raw = []

    tables_out: list[dict[str, Any]] = []
    for t in tables_raw[:max_tables]:
        if not isinstance(t, dict):
            continue
        name = str(t.get("name") or "").strip()[:60]
        headers = t.get("headers")
        rows = t.get("rows")
        if not headers or not isinstance(headers, list):
            continue
        if not rows or not isinstance(rows, list):
            continue
        # Normalise rows: ensure each is a list with the same width as headers (pad / truncate)
        norm_rows: list[list[Any]] = []
        n_cols = len(headers)
        for r in rows:
            if not isinstance(r, list):
                continue
            row = list(r[:n_cols])
            while len(row) < n_cols:
                row.append(None)
            norm_rows.append(row)
        if not norm_rows:
            continue

        source_page = t.get("source_page")
        source_section_id = t.get("source_section_id")

        # Build attribution by resolving page → section if possible
        attribution = {
            "document_id": document_id,
            "section_id": source_section_id,
            "page_numbers": [int(source_page)] if isinstance(source_page, int) else [],
        }

        tables_out.append({
            "name": name or f"Table {len(tables_out) + 1}",
            "headers": [str(h) for h in headers],
            "rows": norm_rows,
            "source_page": (int(source_page) if isinstance(source_page, int) else None),
            "row_count": len(norm_rows),
            "column_types": list(t.get("column_types") or []),
            "attribution": attribution,
        })

    result = {
        "document_id": document_id,
        "title": doc.title,
        "table_count": len(tables_out),
        "tables": tables_out,
        "model": model,
    }

    try:
        await persist_skill_invocation(
            skill="extract-tabular-data", model=model, workspace_id=None,
            inputs={"document_id": document_id, "max_tables": max_tables, "hint": hint},
            outputs={"table_count": len(tables_out),
                     "table_names": [t["name"] for t in tables_out]},
            status="ok", error_message=None,
            duration_ms=int((time.time() - t0) * 1000),
        )
    except Exception:
        pass

    return result
