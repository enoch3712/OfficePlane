---
name: document-edit
description: Apply insert/replace/delete operations to a workspace document.json by node_id
model: deepseek/deepseek-v4-flash
tier: flash
inputs:
  - name: workspace_id
    type: str
    required: true
    description: Workspace directory under /data/workspaces/<workspace_id>/ containing document.json
  - name: operation
    type: str
    required: true
    description: "insert_after | insert_before | insert_as_child | replace | delete"
  - name: anchor_id
    type: str
    required: false
    description: For insert_after / insert_before — sibling anchor node id
  - name: target_id
    type: str
    required: false
    description: For replace / delete — node id to mutate
  - name: parent_id
    type: str
    required: false
    description: For insert_as_child — parent section id
  - name: position
    type: int
    required: false
    description: For insert_as_child — index inside parent.children (default = append)
  - name: node
    type: dict
    required: false
    description: For insert_* / replace — new node JSON to insert
outputs:
  - name: operation
    type: str
  - name: affected_node_id
    type: str
  - name: document_path
    type: str
  - name: revision
    type: int
---

# document-edit

Applies a single structural mutation (insert, replace, or delete) to the
`document.json` stored in a workspace directory.  All operations are
identified by node `id` — the same stable string ids produced by
`parse_document` and stored in `document.json`.

## Workspace layout

```
/data/workspaces/<workspace_id>/
    document.json       ← read + written by this skill
```

The `CONTENT_AGENT_WORKSPACE` environment variable overrides the `/data/workspaces`
root (useful for tests).

## Operations

### insert_after
Insert a new node immediately after the sibling identified by `anchor_id`.

Required inputs: `anchor_id`, `node`

```json
{
  "operation": "insert_after",
  "anchor_id": "p1",
  "node": {"type": "paragraph", "id": "p2", "text": "New paragraph."}
}
```

### insert_before
Insert a new node immediately before the sibling identified by `anchor_id`.

Required inputs: `anchor_id`, `node`

```json
{
  "operation": "insert_before",
  "anchor_id": "p1",
  "node": {"type": "paragraph", "id": "p0", "text": "Prepended paragraph."}
}
```

### insert_as_child
Append (or insert at `position`) a node into the children of a `Section`
identified by `parent_id`.

Required inputs: `parent_id`, `node`
Optional inputs: `position` (integer index; omit to append)

```json
{
  "operation": "insert_as_child",
  "parent_id": "s2",
  "node": {"type": "paragraph", "id": "b1", "text": "Body text."},
  "position": 0
}
```

### replace
Swap the node identified by `target_id` with a new node, preserving sibling order.

Required inputs: `target_id`, `node`

```json
{
  "operation": "replace",
  "target_id": "p1",
  "node": {"type": "paragraph", "id": "p1", "text": "Updated text."}
}
```

### delete
Remove the node identified by `target_id` from its parent's children.

Required inputs: `target_id`

```json
{
  "operation": "delete",
  "target_id": "p1"
}
```

## Revision tracking

Each successful write bumps the `revision` integer at the root of `document.json`
(default 0 → 1, etc.).  The current revision is returned in the output.

## Error handling

- `ValueError` — unknown `operation` name, or a required input is missing for
  the chosen operation.
- `FileNotFoundError` — `document.json` does not exist in the workspace.
- `ValueError("node_id not found: ...")` — the supplied `anchor_id`, `target_id`,
  or `parent_id` does not exist in the document tree.
