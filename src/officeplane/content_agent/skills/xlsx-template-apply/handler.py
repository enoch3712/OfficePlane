"""xlsx-template-apply — fill a saved template with new data + render .xlsx."""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any

from officeplane.content_agent.persistence import persist_skill_invocation
from officeplane.content_agent.renderers.workbook import parse_workbook
from officeplane.content_agent.renderers.xlsx_render import render_xlsx

log = logging.getLogger("officeplane.skills.xlsx-template-apply")


TEMPLATES_ROOT = Path("/data/templates")


def _inject_rows(workbook: dict[str, Any], tables: dict[str, list[list[Any]]]) -> int:
    """Fill in rows for every table whose name matches a key in `tables`.
    Returns count of tables filled."""
    filled = 0
    for sh in (workbook.get("sheets") or []):
        for sec in (sh.get("sections") or []):
            if isinstance(sec, dict) and sec.get("type") == "table":
                name = sec.get("name") or sec.get("id")
                if name in tables and isinstance(tables[name], list):
                    sec["rows"] = [list(r) for r in tables[name] if isinstance(r, list)]
                    filled += 1
    return filled


async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    t0 = time.time()
    template_id = str(inputs.get("template_id") or "").strip()
    tables = inputs.get("tables")
    title_override = inputs.get("title")
    if not template_id:
        raise ValueError("template_id is required")
    if not isinstance(tables, dict):
        raise ValueError("tables must be an object of {table_name: list[list]}")

    templates_root = Path(os.getenv("OFFICEPLANE_TEMPLATES_ROOT") or TEMPLATES_ROOT)
    template_path = templates_root / f"{template_id}.json"
    if not template_path.exists():
        raise FileNotFoundError(f"template not found: {template_id}")

    payload = json.loads(template_path.read_text())
    workbook_dict = payload.get("workbook") or {}
    if title_override:
        workbook_dict.setdefault("meta", {})["title"] = str(title_override)

    filled = _inject_rows(workbook_dict, tables)
    if filled == 0:
        raise ValueError(
            "no table names matched. Template tables: "
            + ", ".join(sec.get("name") or sec.get("id") for sh in (workbook_dict.get("sheets") or [])
                        for sec in (sh.get("sections") or []) if sec.get("type") == "table")
        )

    wb = parse_workbook(workbook_dict)
    xlsx_bytes = render_xlsx(wb)

    job_id = str(uuid.uuid4())
    workspace = Path(os.getenv("CONTENT_AGENT_WORKSPACE", "/data/workspaces")) / job_id
    workspace.mkdir(parents=True, exist_ok=True)
    out_path = workspace / "output.xlsx"
    out_path.write_bytes(xlsx_bytes)

    sheet_count = len(wb.sheets)
    table_count = sum(1 for sh in wb.sheets for s in sh.sections if getattr(s, "type", None) == "table")
    title = wb.meta.title or payload.get("name") or "Untitled"

    result = {
        "file_path": str(out_path),
        "file_url": f"/data/workspaces/{job_id}/output.xlsx",
        "title": title,
        "template_id": template_id,
        "sheet_count": sheet_count,
        "table_count": table_count,
    }
    try:
        await persist_skill_invocation(
            skill="xlsx-template-apply", model=None, workspace_id=job_id,
            inputs={"template_id": template_id, "tables_filled": filled, "title": title_override},
            outputs=result, status="ok", error_message=None,
            duration_ms=int((time.time() - t0) * 1000),
        )
    except Exception:
        pass
    return result
