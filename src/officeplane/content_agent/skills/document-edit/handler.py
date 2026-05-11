"""Handler for the document-edit skill.

Applies insert/replace/delete operations to a workspace's document.json,
anchoring mutations by node id.

Entry point: ``execute(*, inputs, **_)`` — consumed by SkillExecutor.
"""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

from officeplane.content_agent.document_ops import (
    delete_node,
    insert_after,
    insert_as_child,
    insert_before,
    replace_node,
)
from officeplane.content_agent.persistence import (
    persist_edit_revision,
    persist_skill_invocation,
)
from officeplane.content_agent.renderers.document import (
    document_to_dict,
    parse_document,
)

log = logging.getLogger("officeplane.skills.document-edit")

_VALID_OPERATIONS = frozenset(
    {"insert_after", "insert_before", "insert_as_child", "replace", "delete"}
)


async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    """Apply a single structural mutation to a workspace document.json.

    Args:
        inputs: Skill inputs dict — see SKILL.md for the full schema.

    Returns:
        Dict with operation, affected_node_id, document_path, revision.

    Raises:
        ValueError: on invalid operation name or missing required inputs.
        FileNotFoundError: if document.json is absent in the workspace.
    """
    t0 = time.time()
    workspace_id: str = str(inputs.get("workspace_id") or "").strip()
    operation: str = str(inputs.get("operation") or "").strip()

    try:
        if not workspace_id:
            raise ValueError("workspace_id is required")
        if not operation:
            raise ValueError("operation is required")
        if operation not in _VALID_OPERATIONS:
            raise ValueError(
                f"operation must be one of {sorted(_VALID_OPERATIONS)}, got {operation!r}"
            )

        # Resolve workspace path
        workspace_root = Path(os.getenv("CONTENT_AGENT_WORKSPACE", "/data/workspaces"))
        workspace_dir = workspace_root / workspace_id
        doc_path = workspace_dir / "document.json"

        if not doc_path.exists():
            raise FileNotFoundError(
                f"document.json not found in workspace {workspace_id!r}: {doc_path}"
            )

        # Load + parse
        raw: dict = json.loads(doc_path.read_text())
        doc = parse_document(raw)

        # Build new node when the operation needs one
        new_node = None
        node_dict: dict | None = inputs.get("node")
        if node_dict is not None:
            # Lean on parse_document's existing parser for all block/section types.
            wrapper = parse_document({"type": "document", "children": [node_dict]})
            if not wrapper.children:
                raise ValueError("node dict could not be parsed into a known block type")
            new_node = wrapper.children[0]

        # Dispatch
        affected_id: str
        anchor_id: str = ""
        target_id: str = ""
        parent_id: str = ""
        position: int | None = None

        try:
            if operation == "insert_after":
                anchor_id = str(inputs.get("anchor_id") or "")
                if not anchor_id:
                    raise ValueError("anchor_id is required for insert_after")
                if new_node is None:
                    raise ValueError("node is required for insert_after")
                insert_after(doc, anchor_id, new_node)
                affected_id = new_node.id

            elif operation == "insert_before":
                anchor_id = str(inputs.get("anchor_id") or "")
                if not anchor_id:
                    raise ValueError("anchor_id is required for insert_before")
                if new_node is None:
                    raise ValueError("node is required for insert_before")
                insert_before(doc, anchor_id, new_node)
                affected_id = new_node.id

            elif operation == "insert_as_child":
                parent_id = str(inputs.get("parent_id") or "")
                if not parent_id:
                    raise ValueError("parent_id is required for insert_as_child")
                if new_node is None:
                    raise ValueError("node is required for insert_as_child")
                position = inputs.get("position")
                insert_as_child(doc, parent_id, new_node, position)
                affected_id = new_node.id

            elif operation == "replace":
                target_id = str(inputs.get("target_id") or "")
                if not target_id:
                    raise ValueError("target_id is required for replace")
                if new_node is None:
                    raise ValueError("node is required for replace")
                replace_node(doc, target_id, new_node)
                affected_id = new_node.id

            else:  # delete
                target_id = str(inputs.get("target_id") or "")
                if not target_id:
                    raise ValueError("target_id is required for delete")
                delete_node(doc, target_id)
                affected_id = target_id

        except KeyError as exc:
            raise ValueError(f"node_id not found: {exc}") from exc

        # Serialise + save, bumping revision
        out_dict = document_to_dict(doc)
        revision: int = int(raw.get("revision", 0)) + 1
        out_dict["revision"] = revision
        doc_path.write_text(json.dumps(out_dict, indent=2))

        log.info(
            "document-edit %s workspace=%s affected=%s revision=%d",
            operation,
            workspace_id,
            affected_id,
            revision,
        )

        result_dict = {
            "operation": operation,
            "affected_node_id": affected_id,
            "document_path": str(doc_path),
            "revision": revision,
        }

        # Persist edit revision row
        new_rev_id, rev_n = await persist_edit_revision(
            workspace_id=workspace_id,
            op=operation,
            payload={
                "anchor_id": anchor_id,
                "target_id": target_id,
                "parent_id": parent_id,
                "position": position,
                "node_id": affected_id,
            },
            actor="user",
            snapshot_path=str(doc_path),
        )

        await persist_skill_invocation(
            skill="document-edit",
            model=None,
            workspace_id=workspace_id,
            inputs=inputs,
            outputs=result_dict,
            status="ok",
            error_message=None,
            duration_ms=int((time.time() - t0) * 1000),
        )
        return result_dict

    except Exception as e:
        await persist_skill_invocation(
            skill="document-edit",
            model=None,
            workspace_id=workspace_id or None,
            inputs=inputs,
            outputs={},
            status="error",
            error_message=str(e),
            duration_ms=int((time.time() - t0) * 1000),
        )
        raise
