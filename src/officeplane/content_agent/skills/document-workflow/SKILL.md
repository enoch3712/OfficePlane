---
name: document-workflow
description: Drive an approval or sign-off state machine on a document through defined workflow actions.
inputs:
  - name: document_id
    type: string
    required: true
    description: UUID of the Document whose workflow state to advance.
  - name: action
    type: string
    required: true
    description: Workflow action — e.g. "submit", "approve", "reject", "withdraw".
  - name: comment
    type: string
    required: false
    description: Optional reviewer comment attached to the state transition.
outputs:
  - name: new_state
    type: string
    description: Workflow state after the transition (e.g. "PENDING_REVIEW", "APPROVED", "REJECTED").
  - name: task_id
    type: string
    description: UUID of the Task row tracking this workflow step.
tools:
  - db-query
---

# document-workflow

## When to use
Invoke this skill when a document needs to move through a review or approval cycle — for
example, when the user submits a policy draft for sign-off or when an approver accepts or
rejects a submission. Do not use it for content edits; use `document-summarize` or
`document-redact` for those.

## How it works
- Load the current workflow state from the `Task` row linked to `document_id` via
  `db-query`.
- Validate that `action` is a legal transition from the current state; reject invalid
  transitions with an error.
- Advance the `Task.status` and write a `TaskRetry` record if the action is a rejection
  requiring re-submission.
- Attach the optional `comment` to the transition record and update `Document.updated_at`.

## Audit
Emits one `ExecutionHistory` row with `event_type=DOCUMENT_EDITED` and `actor_type=agent`
on each successful state transition.
