"""GET /api/workspaces/{workspace_id}/diff?from=N&to=M — structured tree diff."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from prisma import Prisma

router = APIRouter(prefix="/api/workspaces", tags=["diff"])
log = logging.getLogger("officeplane.api.diff")

WORKSPACES_ROOT = Path("/data/workspaces")


@router.get("/{workspace_id}/diff")
async def get_revision_diff(
    workspace_id: str,
    from_: int = Query(..., alias="from", ge=1),
    to: int = Query(..., ge=1),
):
    if from_ == to:
        raise HTTPException(status_code=400, detail="from and to must differ")

    db = Prisma()
    await db.connect()
    try:
        rev_from = await db.documentrevision.find_first(
            where={"workspaceId": workspace_id, "revisionNumber": from_},
        )
        rev_to = await db.documentrevision.find_first(
            where={"workspaceId": workspace_id, "revisionNumber": to},
        )
        if not rev_from or not rev_to:
            raise HTTPException(status_code=404, detail="revision not found")
    finally:
        await db.disconnect()

    doc_from = _load_snapshot(workspace_id, rev_from)
    doc_to = _load_snapshot(workspace_id, rev_to)
    if doc_from is None or doc_to is None:
        raise HTTPException(status_code=404, detail="snapshot file missing for one of the revisions")

    diff = _compute_diff(doc_from, doc_to)
    return {
        "workspace_id": workspace_id,
        "from_revision": from_,
        "to_revision": to,
        "from_op": rev_from.op,
        "to_op": rev_to.op,
        "diff": diff,
    }


def _load_snapshot(workspace_id: str, rev) -> dict[str, Any] | None:
    """Find the on-disk snapshot for a given revision."""
    candidates = []
    if rev.snapshotPath:
        candidates.append(Path(rev.snapshotPath))
    candidates.append(WORKSPACES_ROOT / workspace_id / "revisions" / f"{rev.revisionNumber}.json")
    if rev.revisionNumber == 1:
        candidates.append(WORKSPACES_ROOT / workspace_id / "document.json")
    for p in candidates:
        if p.exists():
            try:
                return json.loads(p.read_text())
            except json.JSONDecodeError as e:
                log.warning("invalid snapshot %s: %s", p, e)
    return None


def _flatten(doc: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Flatten a Document tree into {node_id: node_dict_with_parent_id}."""
    out: dict[str, dict[str, Any]] = {}

    def walk(node: dict[str, Any], parent_id: str | None):
        nid = node.get("id")
        if not nid:
            return
        entry = {k: v for k, v in node.items() if k != "children" and k != "items"}
        entry["parent_id"] = parent_id
        out[nid] = entry
        for c in (node.get("children") or []):
            walk(c, nid)
        for it in (node.get("items") or []):
            walk(it, nid)

    for top in (doc.get("children") or []):
        walk(top, None)
    return out


def _compute_diff(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    """Compute added / removed / changed node lists between two Document trees."""
    flat_a = _flatten(a)
    flat_b = _flatten(b)

    a_ids = set(flat_a.keys())
    b_ids = set(flat_b.keys())

    added = sorted(b_ids - a_ids)
    removed = sorted(a_ids - b_ids)
    common = a_ids & b_ids

    changed = []
    for nid in sorted(common):
        if flat_a[nid] != flat_b[nid]:
            changed.append({
                "id": nid,
                "type": flat_b[nid].get("type"),
                "before": flat_a[nid],
                "after": flat_b[nid],
            })

    return {
        "added": [
            {"id": nid, "type": flat_b[nid].get("type"),
             "parent_id": flat_b[nid].get("parent_id"),
             "node": flat_b[nid]}
            for nid in added
        ],
        "removed": [
            {"id": nid, "type": flat_a[nid].get("type"),
             "parent_id": flat_a[nid].get("parent_id"),
             "node": flat_a[nid]}
            for nid in removed
        ],
        "changed": changed,
        "summary": {
            "added_count": len(added),
            "removed_count": len(removed),
            "changed_count": len(changed),
        },
    }
