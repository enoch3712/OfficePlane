---
sidebar_position: 8
title: Editing Documents In Place
---

# Editing Documents In Place

The `document-edit` skill applies structural changes to an existing document by targeting nodes using their stable `id`. Every edit is non-destructive: the original state is captured in a `DocumentRevision` row before any mutation is applied.

## The Five Operations

| Operation | What It Does |
|-----------|-------------|
| `insert_after` | Insert a new block or section immediately after the target node |
| `insert_before` | Insert a new block or section immediately before the target node |
| `insert_as_child` | Append a new block or section as the last child of the target section |
| `replace` | Replace the target node's content or type with new data |
| `delete` | Remove the target node and all its descendants |

Node `id` is always the anchor. Positional indexes are never used because they are fragile under concurrent edits and make operations non-composable. Every node created by the generation or ingestion pipeline has a stable UUID-style `id` that persists across revisions.

---

## API

```bash
POST /api/jobs/invoke/document-edit
Content-Type: application/json
```

---

### `insert_after`

Insert a paragraph after block `blk_02`:

```json
{
  "document_id": "doc_01j2kqx8v",
  "operation": "insert_after",
  "target_node_id": "blk_02",
  "node": {
    "type": "paragraph",
    "content": "This paragraph was added after the introduction."
  }
}
```

---

### `insert_before`

Insert a callout before the first table:

```json
{
  "document_id": "doc_01j2kqx8v",
  "operation": "insert_before",
  "target_node_id": "blk_10",
  "node": {
    "type": "callout",
    "content": "Note: All figures in the following table are preliminary."
  }
}
```

---

### `insert_as_child`

Append a new section as the last child of section `sec_02`:

```json
{
  "document_id": "doc_01j2kqx8v",
  "operation": "insert_as_child",
  "target_node_id": "sec_02",
  "node": {
    "type": "section",
    "title": "Appendix A",
    "depth": 1,
    "blocks": [
      { "type": "heading", "level": 2, "content": "Appendix A: Supporting Data" },
      { "type": "paragraph", "content": "See attached workbook for raw figures." }
    ]
  }
}
```

---

### `replace`

Replace the content of a heading block:

```json
{
  "document_id": "doc_01j2kqx8v",
  "operation": "replace",
  "target_node_id": "blk_01",
  "node": {
    "type": "heading",
    "level": 1,
    "content": "Introduction (Revised)"
  }
}
```

You can also change the `type` during a replace — for example, converting a `paragraph` to a `callout`.

---

### `delete`

Delete a section and all its content:

```json
{
  "document_id": "doc_01j2kqx8v",
  "operation": "delete",
  "target_node_id": "sec_02_01"
}
```

Deleted nodes cannot be recovered through normal API operations, but their content is preserved in the `DocumentRevision` patch and can be restored by reverting to a prior revision.

---

## Response

All edit operations return 202 and a job ID:

```json
{
  "job_id": "job_01j3edit",
  "status": "queued",
  "stream_url": "/api/jobs/job_01j3edit/stream",
  "skill": "document-edit"
}
```

When the job completes, the stream emits:

```
event: stop
data: {"job_id": "job_01j3edit", "document_id": "doc_01j2kqx8v", "revision_id": "rev_03", "duration_ms": 820}
```

---

## Round-Trip: Edit → Re-render

Edits update the persisted document tree. Re-rendering produces an updated binary file:

```
original document.json
        │
        ▼
  document-edit (operation: replace blk_02)
        │
        ▼
  updated document.json  ──>  output.docx  (re-rendered)
                          ──>  output.pptx (if pptx document)
```

Trigger a re-render explicitly:

```bash
POST /api/jobs/invoke/export-document
{
  "document_id": "doc_01j2kqx8v",
  "format": "docx"
}
```

The renderer always reads from the current document tree, so the exported file reflects every applied revision.

---

## Revision Tracking

Every successful edit appends a `DocumentRevision` row:

```json
{
  "id": "rev_03",
  "document_id": "doc_01j2kqx8v",
  "parent_revision_id": "rev_02",
  "operation": "replace",
  "target_node_id": "blk_01",
  "patch": {
    "before": { "type": "heading", "level": 1, "content": "Introduction" },
    "after":  { "type": "heading", "level": 1, "content": "Introduction (Revised)" }
  },
  "skill_name": "document-edit",
  "created_at": "2026-05-11T16:45:00Z"
}
```

The full revision DAG is visible at `/api/documents/{id}/lineage`. See [Source Trail: Provenance & Lineage](/architecture/provenance-and-lineage) for the data model and how to interpret the graph.

---

## Batch Edits

To apply multiple operations atomically, use `document-edit-batch`:

```bash
POST /api/jobs/invoke/document-edit-batch
{
  "document_id": "doc_01j2kqx8v",
  "operations": [
    {
      "operation": "replace",
      "target_node_id": "blk_01",
      "node": { "type": "heading", "level": 1, "content": "Introduction (Final)" }
    },
    {
      "operation": "delete",
      "target_node_id": "blk_05"
    },
    {
      "operation": "insert_after",
      "target_node_id": "blk_08",
      "node": { "type": "paragraph", "content": "Added conclusion paragraph." }
    }
  ]
}
```

All operations in a batch are applied within a single database transaction. If any operation fails, the entire batch is rolled back and the document is unchanged.
