"""analyze-xlsx — find issues in an ingested .xlsx document via DeepSeek."""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any

import litellm
from prisma import Prisma

from officeplane.content_agent.persistence import persist_skill_invocation

log = logging.getLogger("officeplane.skills.analyze-xlsx")


PROMPT = """You are auditing an Excel workbook for problems. Read the worksheet
content below and identify issues. Return STRICT JSON.

CATEGORIES (use exactly these strings):
- formula_error    — formula returns #REF!, #DIV/0!, #VALUE!, or references a non-existent cell
- suspected_typo   — a number that looks off-by-magnitude (e.g. 12000 in a column of single-digit %)
- outlier          — a value that is dramatically larger or smaller than its peers in the same column
- missing_total    — a column of numeric values with no totals row when one is expected
- dead_reference   — a formula references a cell or sheet that doesn't exist
- inconsistent_format — mixed text and numbers in a column, or inconsistent units

SEVERITY: "high" | "medium" | "low".

WORKBOOK title: {title}
Source pages (each one is a worksheet):

{pages_blob}

Respond with ONLY a JSON object of this shape:
{{
  "issues": [
    {{"severity": "high|medium|low",
      "category": "<one of the categories above>",
      "sheet": "<worksheet name or null>",
      "cell": "<A1-style cell ref or null>",
      "description": "<short human-readable problem>",
      "suggestion": "<short proposed fix or check>"}}
  ]
}}

Cap the list at {max_issues}. If nothing is wrong, return {{"issues": []}}.
"""


async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    t0 = time.time()
    document_id = str(inputs.get("document_id") or "").strip()
    _raw_max = inputs.get("max_issues")
    max_issues = int(_raw_max) if _raw_max is not None else 20
    if not document_id:
        raise ValueError("document_id is required")
    if max_issues < 1 or max_issues > 100:
        raise ValueError("max_issues must be 1..100")

    db = Prisma()
    await db.connect()
    try:
        doc = await db.document.find_unique(where={"id": document_id})
        if not doc:
            raise ValueError(f"document not found: {document_id}")

        fmt = (doc.sourceFormat or "").lower()
        if fmt not in ("xlsx", "xls"):
            raise ValueError(
                f"analyze-xlsx requires an Excel document; document {document_id} has format '{fmt}'"
            )

        # Pull pages (one per sheet under Phase 33)
        chapters = await db.chapter.find_many(
            where={"documentId": doc.id}, order={"orderIndex": "asc"}
        )
        pages_text: list[str] = []
        sheet_count = 0
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
                        pages_text.append(p.content[:4000])  # cap each page
                        sheet_count += 1

        if not pages_text:
            # Fallback: page rows directly under the doc (older shape)
            pgs = await db.page.find_many(where={"documentId": doc.id}, order={"pageNumber": "asc"})
            for p in pgs:
                if p.content:
                    pages_text.append(p.content[:4000])
                    sheet_count += 1
    finally:
        await db.disconnect()

    if not pages_text:
        return {
            "document_id": document_id, "title": doc.title,
            "sheet_count": 0, "issue_count": 0, "issues": [],
            "model": "skipped", "note": "no page content available to analyse",
        }

    pages_blob = "\n\n--- next sheet ---\n\n".join(pages_text)
    prompt = PROMPT.format(title=doc.title, pages_blob=pages_blob, max_issues=max_issues)
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

    issues_raw = data.get("issues") or []
    if not isinstance(issues_raw, list):
        issues_raw = []
    # Normalise + cap
    issues = []
    valid_severity = {"high", "medium", "low"}
    valid_category = {"formula_error", "suspected_typo", "outlier", "missing_total",
                      "dead_reference", "inconsistent_format"}
    for it in issues_raw[:max_issues]:
        if not isinstance(it, dict):
            continue
        sev = str(it.get("severity") or "low").lower()
        cat = str(it.get("category") or "").lower()
        if sev not in valid_severity:
            sev = "low"
        if cat not in valid_category:
            continue
        issues.append({
            "severity": sev,
            "category": cat,
            "sheet": (str(it["sheet"]) if it.get("sheet") else None),
            "cell": (str(it["cell"]) if it.get("cell") else None),
            "description": str(it.get("description") or "")[:500],
            "suggestion": str(it.get("suggestion") or "")[:500],
        })

    result = {
        "document_id": document_id,
        "title": doc.title,
        "sheet_count": sheet_count,
        "issue_count": len(issues),
        "issues": issues,
        "model": model,
    }

    try:
        await persist_skill_invocation(
            skill="analyze-xlsx", model=model, workspace_id=None,
            inputs={"document_id": document_id, "max_issues": max_issues},
            outputs={"issue_count": len(issues), "sheet_count": sheet_count},
            status="ok", error_message=None,
            duration_ms=int((time.time() - t0) * 1000),
        )
    except Exception:
        pass

    return result
