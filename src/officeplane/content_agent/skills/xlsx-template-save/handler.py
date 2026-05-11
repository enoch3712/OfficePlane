"""xlsx-template-save — save a Workbook shape as a reusable template."""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from officeplane.content_agent.persistence import persist_skill_invocation

log = logging.getLogger("officeplane.skills.xlsx-template-save")


TEMPLATES_ROOT = Path("/data/templates")


def _strip_data_rows(workbook: dict[str, Any]) -> tuple[dict[str, Any], int, int]:
    """Return (workbook_with_empty_rows, sheet_count, table_count)."""
    sheets = workbook.get("sheets") or []
    table_count = 0
    for sh in sheets:
        for sec in sh.get("sections") or []:
            if isinstance(sec, dict) and sec.get("type") == "table":
                sec["rows"] = []
                table_count += 1
    return workbook, len(sheets), table_count


async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    t0 = time.time()
    workspace_id = str(inputs.get("workspace_id") or "").strip()
    name = str(inputs.get("name") or "").strip()
    description = (inputs.get("description") or None)
    if not workspace_id:
        raise ValueError("workspace_id is required")
    if not name:
        raise ValueError("name is required")

    workspace_root = Path(os.getenv("CONTENT_AGENT_WORKSPACE", "/data/workspaces"))
    doc_path = workspace_root / workspace_id / "document.json"
    if not doc_path.exists():
        raise FileNotFoundError(f"document.json not found at {doc_path}")

    workbook = json.loads(doc_path.read_text())
    if workbook.get("type") != "workbook":
        raise ValueError(
            f"expected a workbook document.json, got type={workbook.get('type')!r}"
        )

    stripped, sheet_count, table_count = _strip_data_rows(workbook)

    template_id = uuid.uuid4().hex[:12]
    out_dir = Path(os.getenv("OFFICEPLANE_TEMPLATES_ROOT") or TEMPLATES_ROOT)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{template_id}.json"

    payload = {
        "template_id": template_id,
        "name": name,
        "description": description,
        "created_at": datetime.now(tz=timezone.utc).isoformat(),
        "from_workspace_id": workspace_id,
        "workbook": stripped,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))

    result = {
        "template_id": template_id, "name": name, "path": str(out_path),
        "sheet_count": sheet_count, "table_count": table_count,
    }
    try:
        await persist_skill_invocation(
            skill="xlsx-template-save", model=None, workspace_id=workspace_id,
            inputs={"workspace_id": workspace_id, "name": name},
            outputs=result, status="ok", error_message=None,
            duration_ms=int((time.time() - t0) * 1000),
        )
    except Exception:
        pass
    return result
