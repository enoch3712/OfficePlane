---
name: document-classify
description: Apply a taxonomy label, sensitivity, and retention bucket to a document.
inputs:
  - name: document_id
    type: string
    required: true
    description: UUID of the Document to classify.
  - name: taxonomy
    type: string
    required: true
    description: Target taxonomy namespace (e.g. "iso-15489", "internal").
  - name: force
    type: boolean
    required: false
    description: Overwrite an existing classification if true. Defaults to false.
outputs:
  - name: label
    type: string
    description: Assigned taxonomy label.
  - name: sensitivity
    type: string
    description: Sensitivity tier assigned (e.g. PUBLIC, INTERNAL, CONFIDENTIAL).
  - name: retention_bucket
    type: string
    description: Retention period bucket assigned (e.g. 3Y, 7Y, PERMANENT).
tools:
  - db-query
  - llm-classify
---

# document-classify

## When to use
Invoke this skill when a document has been ingested but lacks a classification, or when
the user asks to re-classify under a new taxonomy. Run before `document-redact` so
sensitivity tier is known, and before `document-workflow` so approval routes can be
chosen by label.

## How it works
- Fetch `Document.summary` and up to 3 `Chapter.summary` rows via `db-query`.
- Send the summaries plus the `taxonomy` namespace to `llm-classify` and receive a
  structured label, sensitivity, and retention bucket.
- Patch the `Document` row with the results via `db-query`.
- If `DocumentInstance` rows exist (derived copies), propagate the sensitivity tier.

## Audit
Emits one `ExecutionHistory` row with `event_type=DOCUMENT_EDITED` and `actor_type=agent`.
