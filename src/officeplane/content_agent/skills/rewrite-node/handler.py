"""rewrite-node — LLM-rewrite a single document node with surrounding context."""
from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import litellm

from officeplane.content_agent.persistence import persist_skill_invocation

log = logging.getLogger("officeplane.skills.rewrite-node")


REWRITABLE_TYPES = {"paragraph", "heading", "callout", "quote", "code"}
MAX_NEIGHBOURS = 4


def _find_node_with_context(doc: dict[str, Any], target_id: str) -> tuple[dict | None, list[dict], dict | None]:
    """Find the target node and its sibling context.
    Returns (target_node, prev_siblings + next_siblings, parent_section).
    """

    def walk(node: dict, parent: dict | None, siblings: list[dict] | None):
        if node.get("id") == target_id:
            return node, parent, siblings or []
        for c in (node.get("children") or []):
            r = walk(c, node, node.get("children"))
            if r[0] is not None:
                return r
        for it in (node.get("items") or []):
            r = walk(it, node, node.get("items"))
            if r[0] is not None:
                return r
        return None, None, None

    top_children = doc.get("children") or []
    for top in top_children:
        node, parent, siblings = walk(top, None, top_children)
        if node is not None:
            # Compute prev/next siblings around the node
            idx = siblings.index(node) if siblings and node in siblings else -1
            prev = siblings[max(0, idx - MAX_NEIGHBOURS):idx] if idx >= 0 else []
            nxt = siblings[idx + 1:idx + 1 + MAX_NEIGHBOURS] if idx >= 0 else []
            return node, prev + nxt, parent
    return None, [], None


def _node_text(node: dict) -> str:
    t = node.get("type")
    if t in ("paragraph", "heading", "quote", "callout", "code"):
        return node.get("text", "") or ""
    if t == "section":
        return node.get("heading", "") or ""
    return ""


def _build_prompt(
    target_node: dict,
    neighbours: list[dict],
    parent: dict | None,
    instruction: str,
    tone: str | None,
) -> str:
    target_type = target_node.get("type")
    target_text = _node_text(target_node)
    neighbour_lines = []
    for n in neighbours:
        nt = _node_text(n)
        if nt:
            neighbour_lines.append(f"- ({n.get('type')}) {nt[:200]}")
    parent_context = ""
    if parent:
        p_heading = parent.get("heading") or _node_text(parent)
        if p_heading:
            parent_context = f"\nContext: This node lives under the section '{p_heading[:120]}'.\n"

    tone_line = f"\nDesired tone: {tone}" if tone else ""

    return (
        f"You are rewriting ONE block in a Microsoft Word / PowerPoint document.\n\n"
        f"Block type: {target_type}\n"
        f"Current text: {target_text}\n"
        f"{parent_context}"
        f"Surrounding blocks (do NOT rewrite these — just for context):\n"
        + ("\n".join(neighbour_lines) if neighbour_lines else "(none)")
        + f"\n\nUser instruction: {instruction}"
        + tone_line
        + "\n\nRespond with a STRICT JSON object representing the REPLACEMENT block. "
          "Keep `id` and `type` from the original. Update `text` (and any relevant fields). "
          "Do not return any other prose, code fences, or commentary. Just the JSON.\n\n"
          f"Original block: {json.dumps(target_node)}\n\n"
          "Replacement block:"
    )


async def execute(*, inputs: dict[str, Any], **_) -> dict[str, Any]:
    t0 = time.time()
    workspace_id = str(inputs.get("workspace_id") or "").strip()
    node_id = str(inputs.get("node_id") or "").strip()
    instruction = str(inputs.get("instruction") or "").strip()
    tone = inputs.get("tone")

    if not workspace_id:
        raise ValueError("workspace_id is required")
    if not node_id:
        raise ValueError("node_id is required")
    if not instruction:
        raise ValueError("instruction is required")

    workspace_root = Path(os.getenv("CONTENT_AGENT_WORKSPACE", "/data/workspaces"))
    doc_path = workspace_root / workspace_id / "document.json"
    if not doc_path.exists():
        raise FileNotFoundError(f"document.json not found at {doc_path}")

    doc_data = json.loads(doc_path.read_text())
    target, neighbours, parent = _find_node_with_context(doc_data, node_id)
    if target is None:
        raise ValueError(f"node_id not found in document: {node_id}")

    ntype = target.get("type")
    if ntype not in REWRITABLE_TYPES:
        raise ValueError(
            f"node type '{ntype}' is not rewritable. Supported: {sorted(REWRITABLE_TYPES)}"
        )

    original_text = _node_text(target)
    if not original_text:
        raise ValueError("target node has no text to rewrite")

    prompt = _build_prompt(target, neighbours, parent, instruction, tone)
    model = os.getenv("OFFICEPLANE_AGENT_MODEL_FLASH", "deepseek/deepseek-v4-flash")

    resp = await litellm.acompletion(
        model=model,
        temperature=0.3,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt}],
    )
    raw = (resp.choices[0].message.content or "{}").strip()
    try:
        rewritten = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"LLM did not return valid JSON: {exc}") from exc

    # Enforce that id + type don't drift
    rewritten["id"] = target.get("id")
    rewritten["type"] = target.get("type")

    result = {
        "workspace_id": workspace_id,
        "node_id": node_id,
        "original_node": target,
        "rewritten_node": rewritten,
        "model": model,
    }

    try:
        await persist_skill_invocation(
            skill="rewrite-node", model=model, workspace_id=workspace_id,
            inputs={"workspace_id": workspace_id, "node_id": node_id,
                    "instruction": instruction[:200], "tone": tone},
            outputs={"node_id": node_id, "original_len": len(original_text),
                     "new_len": len(_node_text(rewritten))},
            status="ok", error_message=None,
            duration_ms=int((time.time() - t0) * 1000),
        )
    except Exception:
        pass

    return result
