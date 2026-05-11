"""Handler for the generate-xlsx skill.

Generates an Excel workbook (.xlsx) from ingested source documents using the
Workbook tree (Workbook → Sheet → Section) with support for tables, charts,
KPI cells, formulas, and typed columns.

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

from officeplane.content_agent.persistence import (
    persist_initial_revision,
    persist_skill_invocation,
)
from officeplane.content_agent.renderers.workbook import parse_workbook, workbook_to_dict
from officeplane.content_agent.renderers.xlsx_render import render_xlsx
from officeplane.content_agent.streaming import emit

log = logging.getLogger("officeplane.skills.generate-xlsx")


# ---------------------------------------------------------------------------
# Prompt template
# ---------------------------------------------------------------------------

PROMPT_TEMPLATE = """You are building an Excel workbook for OfficePlane.

Output a STRICT JSON object conforming to this Workbook schema:

{{
  "type": "workbook",
  "schema_version": "1.0",
  "meta": {{
    "title": "<workbook title>",
    "author": null,
    "description": null,
    "render_hints": {{}}
  }},
  "sheets": [
    {{
      "id": "<short-id>",
      "name": "<Sheet name (max 31 chars)>",
      "freeze_header": true,
      "column_widths": {{}},
      "sections": [
        {{"type": "title", "id": "<id>", "text": "<Sheet Title>", "span_columns": 6}},
        {{"type": "subtitle", "id": "<id>", "text": "<Sub-heading>"}},
        {{"type": "kpi", "id": "<id>", "label": "<Metric Name>", "value": 1234, "format": "currency_usd"}},
        {{"type": "blank", "id": "<id>"}},
        {{
          "type": "table",
          "id": "<table-id>",
          "name": "<TableName>",
          "headers": ["Category", "Value", "Percent"],
          "rows": [
            ["Row A", 100, 0.25],
            ["Row B", 200, 0.50],
            ["Row C", 300, 0.75]
          ],
          "column_formats": ["text", "currency_usd", "percent"],
          "totals_row": ["Total", "=SUM(B2:B4)", null],
          "autofilter": true,
          "style": "TableStyleMedium2"
        }},
        {{
          "type": "chart",
          "id": "<chart-id>",
          "chart_type": "bar",
          "title": "<Chart Title>",
          "data_ref": "<table-id>",
          "categories_col": "Category",
          "values_col": "Value",
          "width_cells": 8,
          "height_cells": 15
        }}
      ]
    }}
  ],
  "attributions": [
    {{
      "node_id": "<table-id or section-id>",
      "document_id": "<source-doc-uuid>",
      "document_title": "<source doc title>",
      "section_id": null,
      "page_numbers": []
    }}
  ]
}}

Section types: title, subtitle, text, blank, table, chart, kpi.
Column formats: text, number, integer, currency_usd, currency_eur, percent, date, datetime.
Chart types: bar, column, line, pie, scatter.

Rules:
- NEVER invent numbers — only use values from the source documents.
- Prefer 1-3 sheets unless data demands more (soft cap: {max_sheets} sheets).
- Propose chart_type that fits: bar for comparisons, line for time-series, pie for ≤6 proportions.
- KPI cells for headline metrics. Use formula references like =SUM(Sheet1!B2:B10) where appropriate.
- Provide at least one attribution per major table pointing back to a source document_id.
- Sheet names must be ≤ 31 characters.
- Table names must be alphanumeric (no spaces); use underscores.
- data_ref in a chart section must match the id of a table section in the same sheet.

Style: {style}
Audience: {audience}

Brief:
{brief}

Source documents:
{source_blob}

Respond with the JSON object only — no prose, no markdown fences.
"""


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

async def execute(*, inputs: dict[str, Any], progress=None, **_) -> dict[str, Any]:
    """Generate a .xlsx from source documents using the Workbook tree.

    Args:
        inputs: Skill inputs dict — see SKILL.md for the full schema.

    Returns:
        Dict with file_path, file_url, title, sheet_count, table_count,
        chart_count, model, source_document_ids.

    Raises:
        ValueError: on invalid inputs or non-JSON LLM response.
    """
    t0 = time.time()
    try:
        source_ids: list[str] = list(inputs.get("source_document_ids") or [])
        brief: str = str(inputs.get("brief") or "").strip()
        style: str = str(inputs.get("style") or "professional").strip()
        audience: str = str(inputs.get("audience") or "general audience").strip()
        max_sheets_raw = inputs.get("max_sheets")
        max_sheets: int = int(max_sheets_raw) if max_sheets_raw is not None else 5

        # --- validation ---
        if not source_ids:
            raise ValueError("source_document_ids is required and must be non-empty")
        if not brief:
            raise ValueError("brief is required")
        await emit(progress, "validating", "Validating inputs")

        # --- load sources ---
        await emit(progress, "loading_sources", f"Loading {len(source_ids)} source document(s)…")
        sources = await _load_sources(source_ids)
        if not sources:
            raise ValueError(
                f"none of the provided source_document_ids resolved: {source_ids}"
            )

        source_blob = _format_source_blob(sources)
        prompt = PROMPT_TEMPLATE.format(
            style=style,
            audience=audience,
            max_sheets=max_sheets,
            brief=brief,
            source_blob=source_blob,
        )

        model = os.getenv("OFFICEPLANE_AGENT_MODEL_FLASH", "deepseek/deepseek-v4-flash")
        log.info("generate-xlsx via %s for sources=%s", model, source_ids)
        await emit(progress, "calling_llm", f"Generating xlsx with {model}…", model=model)

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
        await emit(progress, "parsing", "Parsing generated workbook tree…")

        wb = parse_workbook(data)

        job_id = str(uuid.uuid4())
        workspace_root = Path(os.getenv("CONTENT_AGENT_WORKSPACE", "/data/workspaces"))
        workspace = workspace_root / job_id
        workspace.mkdir(parents=True, exist_ok=True)

        sheet_count = len(wb.sheets)
        table_count = sum(
            1 for sh in wb.sheets for s in sh.sections if getattr(s, "type", None) == "table"
        )
        chart_count = sum(
            1 for sh in wb.sheets for s in sh.sections if getattr(s, "type", None) == "chart"
        )

        await emit(
            progress, "rendering",
            f"Rendering output.xlsx ({sheet_count} sheets, {table_count} tables, {chart_count} charts)…",
            sheet_count=sheet_count,
        )
        xlsx_bytes = render_xlsx(wb, workspace_dir=workspace)

        out_path = workspace / "output.xlsx"
        out_path.write_bytes(xlsx_bytes)

        result_dict = {
            "file_path": str(out_path),
            "file_url": f"/data/workspaces/{job_id}/output.xlsx",
            "title": wb.meta.title or "Untitled",
            "sheet_count": sheet_count,
            "table_count": table_count,
            "chart_count": chart_count,
            "model": model,
            "source_document_ids": source_ids,
        }

        # Snapshot the Workbook JSON for future edits
        (workspace / "document.json").write_text(json.dumps(workbook_to_dict(wb)))

        # Persist provenance + initial revision
        await emit(progress, "persisting", "Recording revision…")
        await persist_initial_revision(
            workspace_id=job_id,
            op="create",
            payload={
                "skill": "generate-xlsx",
                "title": wb.meta.title or "Untitled",
                "sheet_count": sheet_count,
                "table_count": table_count,
                "chart_count": chart_count,
            },
            snapshot_path=str(workspace / "document.json"),
        )
        # Note: persist_derivations_from_document expects a Document with chapter/section
        # attributions. Workbook lineage will be added in Phase 32.
        await persist_skill_invocation(
            skill="generate-xlsx",
            model=model,
            workspace_id=job_id,
            inputs=inputs,
            outputs=result_dict,
            status="ok",
            error_message=None,
            duration_ms=int((time.time() - t0) * 1000),
        )
        await emit(progress, "complete", "Done", **result_dict)
        return result_dict

    except Exception as e:
        await persist_skill_invocation(
            skill="generate-xlsx",
            model=None,
            workspace_id=None,
            inputs=inputs,
            outputs={},
            status="error",
            error_message=str(e),
            duration_ms=int((time.time() - t0) * 1000),
        )
        raise
