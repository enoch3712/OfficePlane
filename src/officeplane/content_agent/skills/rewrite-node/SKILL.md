---
name: rewrite-node
description: Rewrite a single node in a generated document using DeepSeek, given a user instruction and surrounding context. Does NOT mutate the document — caller applies the new node via document-edit replace.
model: deepseek/deepseek-v4-flash
tier: flash
inputs:
  - name: workspace_id
    type: str
    required: true
    description: Workspace directory under /data/workspaces/<id>/ containing document.json
  - name: node_id
    type: str
    required: true
    description: Id of the node to rewrite (must exist in document.json)
  - name: instruction
    type: str
    required: true
    description: What the user wants — e.g. "make this more concise" or "rewrite for a nursing audience"
  - name: tone
    type: str
    required: false
    description: Optional tone override (warm / clinical / authoritative / casual)
outputs:
  - name: workspace_id
    type: str
  - name: node_id
    type: str
  - name: original_node
    type: dict
  - name: rewritten_node
    type: dict
  - name: model
    type: str
---

# rewrite-node

Rewrites a single node in a document using an LLM, incorporating surrounding sibling and parent context to ensure coherence with adjacent content.

## Flow

1. Load `document.json` from `CONTENT_AGENT_WORKSPACE/<workspace_id>/document.json`
2. Locate the target node by `node_id`, collecting up to 4 sibling neighbours before/after and identifying the parent section
3. Build a prompt that includes: node type, current text, parent section heading, surrounding neighbours (read-only context), user instruction, and optional tone
4. Call DeepSeek v4-flash with `response_format=json_object` (temperature=0.3)
5. Parse the JSON response and enforce that `id` and `type` match the original (the LLM may not change the node's structural identity)
6. Return the rewritten node — **does NOT write back to document.json**

## Caller Responsibility

The caller (API layer or UI) must apply the returned `rewritten_node` via the `document-edit` skill with `operation=replace` to preserve audit trail (revision + derivation chain).

## Rewritable Types

Only the following node types are rewritable in v1:
- `paragraph`
- `heading`
- `callout`
- `quote`
- `code`

Attempting to rewrite `table`, `figure`, `list`, `divider`, or `section` nodes raises a `ValueError`.

## Error Conditions

- `workspace_id` missing → `ValueError`
- `node_id` missing → `ValueError`
- `instruction` missing → `ValueError`
- `document.json` not found → `FileNotFoundError`
- Node not found in document → `ValueError`
- Node type not rewritable → `ValueError`
- Node has no text → `ValueError`
- LLM returns invalid JSON → `ValueError`
