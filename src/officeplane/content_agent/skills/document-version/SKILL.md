---
name: document-version
description: Create a new document version, diff against the prior version, or roll back to a previous version.
inputs:
  - name: document_id
    type: string
    required: true
    description: UUID of the Document to version.
  - name: action
    type: string
    required: true
    description: One of "create", "diff", or "rollback".
  - name: target_version
    type: integer
    required: false
    description: Version number to diff against or roll back to. Required for "diff" and "rollback".
outputs:
  - name: version_number
    type: integer
    description: Version number created or active after the operation.
  - name: diff_summary
    type: string
    description: Human-readable diff summary; populated for "diff" action only.
tools:
  - db-query
  - diff-engine
---

# document-version

## When to use
Invoke this skill when the user wants to checkpoint a document after edits, compare two
versions, or undo a recent change. It should be called after any bulk mutation (summarize,
redact, extract) if the user requested version tracking.

## How it works
- For "create": copy the current `Document`, `Chapter`, `Section`, and `Page` state into
  a new `DocumentInstance` row tagged with an incremented version number via `db-query`.
- For "diff": load two `DocumentInstance` snapshots and pass their text to `diff-engine`;
  return a structured change set.
- For "rollback": promote the target `DocumentInstance` snapshot to the current working
  state by overwriting the live `Document` rows via `db-query`.
- Update `Document.current_version` after each write.

## Audit
Emits one `ExecutionHistory` row with `event_type=DOCUMENT_EDITED` and `actor_type=agent`
for "create" and "rollback" actions. "diff" is read-only and emits no row.
