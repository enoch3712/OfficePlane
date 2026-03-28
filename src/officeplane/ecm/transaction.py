"""
Transaction log for ECM session compensation.

Records reversible operations committed during a session's commit phase.
On failure, compensate() walks the log in LIFO order and undoes each op.

Supported ops:
  - move_dir:        shutil.move(src → dst) → compensate by move(dst → src)
  - create_document: db.document.create(id) → compensate by db.document.delete(id)
"""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class TransactionOp:
    op_type: str
    params: dict[str, Any]


class TransactionLog:
    """Append-only log of reversible operations."""

    def __init__(self) -> None:
        self._ops: list[TransactionOp] = []

    def record(self, op_type: str, **params: Any) -> None:
        """Record a committed operation for potential compensation."""
        self._ops.append(TransactionOp(op_type=op_type, params=params))

    async def compensate(self) -> None:
        """Reverse all logged operations in LIFO order."""
        for op in reversed(self._ops):
            try:
                await self._undo(op)
            except Exception as exc:
                log.error("Compensation failed for op %r: %s", op.op_type, exc)

    async def _undo(self, op: TransactionOp) -> None:
        if op.op_type == "move_dir":
            # compensate: move it back
            src = Path(op.params["src"])  # original location to restore to
            dst = Path(op.params["dst"])  # where it currently lives
            if dst.exists():
                shutil.move(str(dst), str(src))
                log.debug("Compensated move_dir: %s → %s", dst, src)

        elif op.op_type == "create_document":
            doc_id = op.params.get("document_id")
            if doc_id:
                try:
                    from officeplane.management.db import get_db
                    db = await get_db()
                    await db.document.delete(where={"id": doc_id})
                    log.debug("Compensated create_document: deleted %s", doc_id)
                except Exception as exc:
                    log.error("Failed to delete document %s during compensation: %s", doc_id, exc)

        else:
            log.warning("No compensation handler for op type %r — skipping", op.op_type)
