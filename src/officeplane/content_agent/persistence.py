"""Provenance + lineage persistence helpers.

Skills call these to write Derivation, DocumentRevision, and SkillInvocation
rows. Failures are logged but never raised — the user-facing skill must not
break because audit persistence had a hiccup.
"""
from __future__ import annotations

import hashlib
import json
import logging
from typing import Any
from uuid import UUID

from prisma import Json, Prisma

log = logging.getLogger("officeplane.persistence")


def prompt_hash(prompt: str) -> str:
    return "sha256:" + hashlib.sha256(prompt.encode("utf-8")).hexdigest()


async def persist_skill_invocation(
    *,
    skill: str,
    model: str | None,
    workspace_id: str | None,
    inputs: dict[str, Any],
    outputs: dict[str, Any],
    status: str,
    error_message: str | None,
    duration_ms: int,
    actor: str | None = None,
) -> str | None:
    """Insert a row into skill_invocations. Returns the new row id or None on failure."""
    db = Prisma()
    try:
        await db.connect()
        row = await db.skillinvocation.create(data={
            "skill": skill,
            "model": model,
            "workspaceId": workspace_id,
            "inputs": Json(json.dumps(_jsonable(inputs))),
            "outputs": Json(json.dumps(_jsonable(outputs))),
            "status": status,
            "errorMessage": error_message,
            "actor": actor,
            "durationMs": duration_ms,
        })
        return row.id
    except Exception as e:
        log.warning("persist_skill_invocation failed: %s", e)
        return None
    finally:
        try:
            await db.disconnect()
        except Exception:
            pass


async def persist_derivations_from_document(
    *,
    workspace_id: str,
    generated_doc_path: str | None,
    doc: Any,
    skill: str,
    model: str,
    prompt: str,
    confidence: float | None = None,
) -> int:
    """Walk the generated Document's ``attributions``, insert a Derivation row per node→source pairing.
    Returns the count inserted."""
    if not doc.attributions:
        return 0
    db = Prisma()
    inserted = 0
    p_hash = prompt_hash(prompt)
    try:
        await db.connect()
        for a in doc.attributions:
            try:
                data: dict[str, Any] = {
                    "workspaceId": workspace_id,
                    "generatedNodeId": a.node_id,
                    "generatedDocPath": generated_doc_path,
                    "sourceDocumentId": a.document_id if _is_uuid(a.document_id) else None,
                    "sourceChapterId": a.chapter_id if _is_uuid(a.chapter_id) else None,
                    "sourceSectionId": a.section_id if _is_uuid(a.section_id) else None,
                    "pageNumbers": list(a.page_numbers or []),
                    "skill": skill,
                    "model": model,
                    "promptHash": p_hash,
                    "confidence": confidence,
                }
                await db.derivation.create(data=data)
                inserted += 1
            except Exception as e:
                log.warning("derivation insert failed for node=%s: %s", a.node_id, e)
        return inserted
    except Exception as e:
        log.warning("persist_derivations_from_document failed: %s", e)
        return inserted
    finally:
        try:
            await db.disconnect()
        except Exception:
            pass


async def persist_initial_revision(
    *,
    workspace_id: str,
    op: str,
    payload: dict[str, Any],
    actor: str | None = None,
    snapshot_path: str | None = None,
) -> str | None:
    """Insert the first (``create``) DocumentRevision for a freshly generated workspace.
    Returns the new row id."""
    db = Prisma()
    try:
        await db.connect()
        row = await db.documentrevision.create(data={
            "workspaceId": workspace_id,
            "parentRevisionId": None,
            "revisionNumber": 1,
            "op": op,
            "payload": Json(json.dumps(_jsonable(payload))),
            "actor": actor or "system",
            "snapshotPath": snapshot_path,
        })
        return row.id
    except Exception as e:
        log.warning("persist_initial_revision failed: %s", e)
        return None
    finally:
        try:
            await db.disconnect()
        except Exception:
            pass


async def persist_edit_revision(
    *,
    workspace_id: str,
    op: str,
    payload: dict[str, Any],
    actor: str | None = None,
    snapshot_path: str | None = None,
) -> tuple[str | None, int]:
    """Append a DocumentRevision under the latest one in this workspace.
    Returns (new_id, revision_number)."""
    db = Prisma()
    try:
        await db.connect()
        # Find latest revision in this workspace
        latest = await db.documentrevision.find_first(
            where={"workspaceId": workspace_id},
            order={"revisionNumber": "desc"},
        )
        parent_id = latest.id if latest else None
        next_n = (latest.revisionNumber + 1) if latest else 1
        row = await db.documentrevision.create(data={
            "workspaceId": workspace_id,
            "parentRevisionId": parent_id,
            "revisionNumber": next_n,
            "op": op,
            "payload": Json(json.dumps(_jsonable(payload))),
            "actor": actor or "user",
            "snapshotPath": snapshot_path,
        })
        return row.id, next_n
    except Exception as e:
        log.warning("persist_edit_revision failed: %s", e)
        return None, 0
    finally:
        try:
            await db.disconnect()
        except Exception:
            pass


def _is_uuid(v: Any) -> bool:
    if not v or not isinstance(v, str):
        return False
    try:
        UUID(v)
        return True
    except (ValueError, TypeError):
        return False


def _jsonable(v: Any) -> Any:
    """Recursively convert dataclasses / sets to JSON-safe types."""
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, (list, tuple, set)):
        return [_jsonable(i) for i in v]
    if isinstance(v, dict):
        return {str(k): _jsonable(val) for k, val in v.items()}
    if hasattr(v, "__dict__"):
        return _jsonable(vars(v))
    return str(v)
