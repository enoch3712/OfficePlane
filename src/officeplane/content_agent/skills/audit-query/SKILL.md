---
name: audit-query
description: Read-only query over the ExecutionHistory table with structured filters.
inputs:
  - name: filters
    type: object
    required: true
    description: Filter object — supports keys document_id, event_type, actor_type, from_ts, to_ts, limit.
outputs:
  - name: events
    type: array
    description: List of matching ExecutionHistory rows ordered by created_at descending.
  - name: total
    type: integer
    description: Total count of matching rows before limit is applied.
tools:
  - db-query
---

# audit-query

## When to use
Invoke this skill when the user asks what happened to a document, who made changes, when
an event occurred, or needs a compliance report. It is the only skill authorized to expose
`ExecutionHistory` rows to the user; do not inline audit data in other skill responses.

## How it works
- Parse the `filters` object and build a parameterized WHERE clause against the
  `ExecutionHistory` table via `db-query`.
- Support filtering by `document_id`, `event_type` enum value, `actor_type`, and a
  timestamp range (`from_ts`, `to_ts`).
- Return rows enriched with `Document.title` joined from the `Document` table.
- Apply `limit` (default 50, max 500) to prevent runaway result sets.

## Audit
Emits no `ExecutionHistory` rows (read-only). This skill must never write to the audit
log to avoid recursive entries.
