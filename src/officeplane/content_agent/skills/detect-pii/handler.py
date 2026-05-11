"""detect-pii — find PII in an ingested document; return redaction plan."""
from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

import litellm
from prisma import Prisma

from officeplane.content_agent.persistence import persist_skill_invocation

log = logging.getLogger("officeplane.skills.detect-pii")

VALID_CATEGORIES = {
    "email", "phone", "us_ssn", "credit_card", "iban",
    "person_name", "address", "dob", "medical_id",
}

# Lazy-import the regex patterns module (sibling file)
def _regex_module():
    p = Path(__file__).parent / "regex_patterns.py"
    spec = importlib.util.spec_from_file_location("detect_pii_regex", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["detect_pii_regex"] = mod
    spec.loader.exec_module(mod)
    return mod


PROMPT = """You are finding sensitive personal information (PII) that simple regex cannot
detect — primarily NAMES OF NATURAL PERSONS, ADDRESSES, DATES OF BIRTH, and
MEDICAL RECORD NUMBERS.

Do NOT report emails, phone numbers, SSN, IBAN, or credit cards — those are
handled by a separate regex pass. Skip generic company / institution names
("General Hospital", "Acme Corp"). Only report real personal names.

Return STRICT JSON only.

CATEGORIES: person_name, address, dob, medical_id

CONFIDENCE: 0.0–1.0 (how certain you are this is PII vs a false positive).
Be conservative — when in doubt, give 0.5 or lower.

Categories filter: {categories_filter}

Document title: {title}

Pages (each numbered):
{pages_blob}

Response shape:
{{
  "findings": [
    {{"category": "...", "value": "...", "page_number": <int>,
      "context": "<surrounding 30-80 chars>", "confidence": 0.8}}
  ]
}}

Cap output at {max_llm} findings.
"""


async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    t0 = time.time()
    document_id = str(inputs.get("document_id") or "").strip()
    categories = inputs.get("categories")
    regex_only = bool(inputs.get("regex_only", False))
    _raw_max = inputs.get("max_findings")
    max_findings = int(_raw_max) if _raw_max is not None else 200

    if not document_id:
        raise ValueError("document_id is required")
    if max_findings < 1 or max_findings > 1000:
        raise ValueError("max_findings must be 1..1000")
    if categories:
        if not isinstance(categories, list):
            raise ValueError("categories must be a list of strings")
        invalid = [c for c in categories if c not in VALID_CATEGORIES]
        if invalid:
            raise ValueError(f"unknown categories: {invalid}. valid: {sorted(VALID_CATEGORIES)}")

    db = Prisma()
    await db.connect()
    try:
        doc = await db.document.find_unique(where={"id": document_id})
        if not doc:
            raise ValueError(f"document not found: {document_id}")

        # Pull pages — same pattern as analyze-xlsx / extract-tabular-data
        chapters = await db.chapter.find_many(
            where={"documentId": doc.id}, order={"orderIndex": "asc"}
        )
        page_records: list[dict[str, Any]] = []
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
                        page_records.append({"page_number": p.pageNumber, "content": p.content[:4000]})
        if not page_records:
            pgs = await db.page.find_many(where={"documentId": doc.id}, order={"pageNumber": "asc"})
            for p in pgs:
                if p.content:
                    page_records.append({"page_number": p.pageNumber, "content": p.content[:4000]})
    finally:
        await db.disconnect()

    findings: list[dict[str, Any]] = []

    # Pass 1: regex
    rx = _regex_module()
    cats_filter: set[str] | None = set(categories) if categories else None
    for pg in page_records:
        for hit in rx.find_regex_pii(pg["content"]):
            if cats_filter and hit["category"] not in cats_filter:
                continue
            findings.append({**hit, "page_number": pg["page_number"]})

    # Pass 2: LLM (unless regex_only)
    model = os.getenv("OFFICEPLANE_AGENT_MODEL_FLASH", "deepseek/deepseek-v4-flash")
    llm_count = 0
    if not regex_only and page_records:
        pages_blob_parts = []
        for pg in page_records:
            pages_blob_parts.append(f"--- Page {pg['page_number']} ---\n{pg['content']}\n")
        pages_blob = "\n".join(pages_blob_parts)
        categories_filter = (
            f"only return: {', '.join(c for c in categories if c in {'person_name','address','dob','medical_id'})}"
            if categories else "report all of: person_name, address, dob, medical_id"
        )
        prompt = PROMPT.format(
            categories_filter=categories_filter,
            title=doc.title,
            pages_blob=pages_blob,
            max_llm=max_findings // 2,
        )
        try:
            resp = await litellm.acompletion(
                model=model,
                temperature=0.0,
                response_format={"type": "json_object"},
                messages=[{"role": "user", "content": prompt}],
            )
            raw = (resp.choices[0].message.content or "{}").strip()
            data = json.loads(raw)
            raw_findings = data.get("findings") or []
            for f in raw_findings:
                if not isinstance(f, dict):
                    continue
                cat = str(f.get("category") or "").lower()
                if cat not in {"person_name", "address", "dob", "medical_id"}:
                    continue
                if cats_filter and cat not in cats_filter:
                    continue
                conf = f.get("confidence")
                try:
                    confidence = float(conf) if conf is not None else 0.5
                except (TypeError, ValueError):
                    confidence = 0.5
                findings.append({
                    "category": cat,
                    "value": str(f.get("value") or "").strip()[:200],
                    "page_number": int(f.get("page_number") or 0) or None,
                    "context": str(f.get("context") or "")[:200] or None,
                    "source": "llm",
                    "confidence": round(confidence, 3),
                })
                llm_count += 1
        except Exception as e:
            log.warning("LLM pass failed: %s", e)

    # Cap + dedup (same value+category+page collapses)
    seen: set[tuple] = set()
    deduped: list[dict[str, Any]] = []
    for f in findings:
        key = (f.get("category"), f.get("value"), f.get("page_number"))
        if key in seen:
            continue
        seen.add(key)
        deduped.append(f)
        if len(deduped) >= max_findings:
            break
    findings = deduped

    # Build redaction plan
    redaction_plan = [
        {
            "page_number": f.get("page_number"),
            "value": f.get("value"),
            "category": f.get("category"),
            "suggested_replacement": _replacement_for(f.get("category", "")),
        }
        for f in findings if f.get("value")
    ]

    category_counts: dict[str, int] = {}
    for f in findings:
        cat = f.get("category") or "unknown"
        category_counts[cat] = category_counts.get(cat, 0) + 1

    result = {
        "document_id": document_id,
        "title": doc.title,
        "finding_count": len(findings),
        "findings": findings,
        "category_counts": category_counts,
        "redaction_plan": redaction_plan,
        "model": model if not regex_only else "regex-only",
        "regex_count": len(findings) - llm_count,
        "llm_count": llm_count,
    }

    try:
        await persist_skill_invocation(
            skill="detect-pii", model=result["model"], workspace_id=None,
            inputs={"document_id": document_id, "categories": categories,
                    "regex_only": regex_only, "max_findings": max_findings},
            outputs={"finding_count": len(findings),
                     "category_counts": category_counts,
                     "regex_count": result["regex_count"],
                     "llm_count": llm_count},
            status="ok", error_message=None,
            duration_ms=int((time.time() - t0) * 1000),
        )
    except Exception:
        pass

    return result


def _replacement_for(category: str) -> str:
    return {
        "email": "[EMAIL]",
        "phone": "[PHONE]",
        "us_ssn": "[SSN]",
        "credit_card": "[CC]",
        "iban": "[IBAN]",
        "person_name": "[PERSON]",
        "address": "[ADDRESS]",
        "dob": "[DOB]",
        "medical_id": "[MEDICAL_ID]",
    }.get(category, "[REDACTED]")
