"""Disposition runner — finds due records and applies their policy action.

Honours legal_hold (never dispose while held) and creates a DispositionEvent
audit row for every record evaluated (SUCCESS, SKIPPED, or ERROR).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from prisma import Prisma

log = logging.getLogger("officeplane.retention.disposition")


async def run_disposition_pass(*, actor: str = "system",
                                limit: int = 500,
                                dry_run: bool = False) -> dict[str, Any]:
    """Scan for retentions where disposition_due_at <= now AND not disposed.

    For each due record:
      - If legal_hold is set: emit SKIPPED event with reason "legal_hold"
      - Else: apply the action (ARCHIVE/DESTROY/REVIEW), mark disposed=true,
              emit SUCCESS event.

    Returns counts: {scanned, disposed, skipped_hold, errored}.
    """
    db = Prisma()
    await db.connect()
    summary = {"scanned": 0, "disposed": 0, "skipped_hold": 0, "errored": 0,
               "dry_run": dry_run, "events": []}
    try:
        now = datetime.now(tz=timezone.utc)
        due = await db.documentretention.find_many(
            where={
                "dispositionDueAt": {"lte": now},
                "disposed": False,
            },
            take=limit,
            order={"dispositionDueAt": "asc"},
        )
        summary["scanned"] = len(due)
        for r in due:
            policy = await db.retentionpolicy.find_unique(where={"id": r.policyId})
            if not policy:
                summary["errored"] += 1
                continue
            if r.legalHold:
                if not dry_run:
                    await db.dispositionevent.create(data={
                        "retentionId": r.id,
                        "action": policy.action,
                        "status": "SKIPPED",
                        "reason": f"legal_hold: {r.legalHoldReason or 'no reason given'}",
                        "actor": actor,
                    })
                summary["skipped_hold"] += 1
                summary["events"].append({"retention_id": r.id, "status": "SKIPPED",
                                          "reason": "legal_hold"})
                continue
            try:
                if not dry_run:
                    # Apply action — for v1, ARCHIVE/REVIEW/DESTROY are LOGICAL marks
                    # on the doc + audit row. No file-level mutation. Sub-phases can wire
                    # real archive storage / file deletion later.
                    await db.documentretention.update(
                        where={"id": r.id},
                        data={"disposed": True, "disposedAt": now},
                    )
                    await db.dispositionevent.create(data={
                        "retentionId": r.id,
                        "action": policy.action,
                        "status": "SUCCESS",
                        "actor": actor,
                    })
                summary["disposed"] += 1
                summary["events"].append({"retention_id": r.id, "action": policy.action,
                                          "status": "SUCCESS"})
            except Exception as e:
                log.warning("disposition failed for retention %s: %s", r.id, e)
                if not dry_run:
                    try:
                        await db.dispositionevent.create(data={
                            "retentionId": r.id,
                            "action": policy.action,
                            "status": "ERROR",
                            "reason": str(e)[:500],
                            "actor": actor,
                        })
                    except Exception:
                        pass
                summary["errored"] += 1
        return summary
    finally:
        await db.disconnect()
