"""populate-xlsx-from-source — extract tables from sources + fill an xlsx template.

Composes:
  1) extract-tabular-data — one call per source document
  2) xlsx-template-apply  — one call with the mapped tables payload

Header-similarity mapping: each template table's headers are compared (lowercased
Jaccard on word tokens) against every extracted table's headers. Best-match
above a threshold wins. Caller can override via the `mapping` input.
"""
from __future__ import annotations

import importlib.util
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any

from officeplane.content_agent.persistence import persist_skill_invocation

log = logging.getLogger("officeplane.skills.populate-xlsx-from-source")

SIMILARITY_THRESHOLD = 0.35


def _load_sibling_handler(skill: str):
    """Dynamically load a sibling skill handler module."""
    candidates = [
        Path(f"/app/src/officeplane/content_agent/skills/{skill}/handler.py"),
        Path(__file__).resolve().parents[2] / f"skills/{skill}/handler.py",
    ]
    for p in candidates:
        if p.exists():
            mod_name = f"sibling_{skill.replace('-', '_')}"
            spec = importlib.util.spec_from_file_location(mod_name, p)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = mod
            spec.loader.exec_module(mod)
            return mod
    raise RuntimeError(f"sibling skill not found: {skill}")


def _jaccard(a: list[str], b: list[str]) -> float:
    sa = {w.strip().lower() for w in a if w}
    sb = {w.strip().lower() for w in b if w}
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _best_match(template_headers: list[str], extracted_tables: list[dict[str, Any]]) -> tuple[dict | None, float]:
    best: tuple[dict | None, float] = (None, 0.0)
    for t in extracted_tables:
        score = _jaccard(template_headers, t.get("headers") or [])
        if score > best[1]:
            best = (t, score)
    return best


async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    t0 = time.time()
    source_ids = list(inputs.get("source_document_ids") or [])
    template_id = str(inputs.get("template_id") or "").strip()
    hint = inputs.get("hint")
    title_override = inputs.get("title")
    explicit_mapping = inputs.get("mapping") or {}
    if not source_ids:
        raise ValueError("source_document_ids is required and must be non-empty")
    if not template_id:
        raise ValueError("template_id is required")
    if not isinstance(explicit_mapping, dict):
        raise ValueError("mapping must be an object {template_table_name: extracted_table_name}")

    # Load template to know its tables
    templates_root = Path(os.getenv("OFFICEPLANE_TEMPLATES_ROOT") or "/data/templates")
    template_path = templates_root / f"{template_id}.json"
    if not template_path.exists():
        raise FileNotFoundError(f"template not found: {template_id}")
    template_doc = json.loads(template_path.read_text())
    workbook = template_doc.get("workbook") or {}
    template_tables: list[dict[str, Any]] = []
    for sh in (workbook.get("sheets") or []):
        for sec in (sh.get("sections") or []):
            if isinstance(sec, dict) and sec.get("type") == "table":
                template_tables.append({
                    "name": sec.get("name") or sec.get("id"),
                    "headers": sec.get("headers") or [],
                })
    if not template_tables:
        raise ValueError(f"template {template_id} has no table sections — nothing to populate")

    # Step 1: extract tables from every source
    extract_handler = _load_sibling_handler("extract-tabular-data")
    all_extracted: list[dict[str, Any]] = []
    for sid in source_ids:
        try:
            r = await extract_handler.execute(inputs={
                "document_id": sid,
                "max_tables": 20,
                "hint": hint,
            })
            for t in (r.get("tables") or []):
                # tag origin for the mapping report
                t = dict(t)
                t["_source_document_id"] = sid
                all_extracted.append(t)
        except Exception as e:
            log.warning("extract failed for %s: %s", sid, e)

    # Step 2: map extracted → template tables
    used_extracted_ids: set[int] = set()  # dedupe by Python id() so the same table isn't reused
    final_tables_payload: dict[str, list[list[Any]]] = {}
    mapping_report: list[dict[str, Any]] = []

    for tpl in template_tables:
        tpl_name = tpl["name"]
        tpl_headers = tpl["headers"]
        chosen = None
        score = 0.0
        # 1) Explicit mapping wins
        if tpl_name in explicit_mapping:
            wanted = explicit_mapping[tpl_name]
            for ex in all_extracted:
                if (ex.get("name") or "") == wanted and id(ex) not in used_extracted_ids:
                    chosen, score = ex, 1.0
                    break
        # 2) Fuzzy by header similarity
        if chosen is None:
            candidates = [ex for ex in all_extracted if id(ex) not in used_extracted_ids]
            chosen, score = _best_match(tpl_headers, candidates)
            if score < SIMILARITY_THRESHOLD:
                chosen = None
        if chosen is not None:
            used_extracted_ids.add(id(chosen))
            final_tables_payload[tpl_name] = chosen.get("rows") or []
            mapping_report.append({
                "template_table": tpl_name,
                "filled_from": chosen.get("name"),
                "source_document_id": chosen.get("_source_document_id"),
                "row_count": len(chosen.get("rows") or []),
                "similarity": round(score, 3),
            })
        else:
            mapping_report.append({
                "template_table": tpl_name,
                "filled_from": None,
                "source_document_id": None,
                "row_count": 0,
                "similarity": 0.0,
            })

    # Bail if nothing matched
    if not final_tables_payload:
        raise ValueError(
            "no extracted tables matched any template table by header similarity "
            f"(threshold={SIMILARITY_THRESHOLD}). Template tables: "
            + ", ".join(t["name"] for t in template_tables)
        )

    # Step 3: apply the template
    apply_handler = _load_sibling_handler("xlsx-template-apply")
    apply_result = await apply_handler.execute(inputs={
        "template_id": template_id,
        "tables": final_tables_payload,
        "title": title_override,
    })

    result = {
        "file_path": apply_result["file_path"],
        "file_url": apply_result["file_url"],
        "title": apply_result["title"],
        "template_id": template_id,
        "source_document_count": len(source_ids),
        "extracted_table_count": len(all_extracted),
        "mapping_report": mapping_report,
        "model": os.getenv("OFFICEPLANE_AGENT_MODEL_FLASH", "deepseek/deepseek-v4-flash"),
    }

    try:
        await persist_skill_invocation(
            skill="populate-xlsx-from-source",
            model=result["model"],
            workspace_id=None,
            inputs={"source_document_ids": source_ids, "template_id": template_id, "hint": hint},
            outputs={
                "file_path": result["file_path"],
                "template_id": template_id,
                "source_document_count": len(source_ids),
                "extracted_table_count": len(all_extracted),
                "tables_filled": sum(1 for r in mapping_report if r["filled_from"]),
            },
            status="ok", error_message=None,
            duration_ms=int((time.time() - t0) * 1000),
        )
    except Exception:
        pass

    return result
