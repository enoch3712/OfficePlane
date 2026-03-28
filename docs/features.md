# OfficePlane — Features

## Document Hooks (Event-Driven Agents)

Hooks let you attach automated agent actions to document lifecycle events.
When a document is created, edited, or has a section changed, OfficePlane
can automatically trigger one or more agents to review, validate, or transform
the content — no manual intervention required.

### Use Cases

- **Legal compliance** — Legal team updates a contract clause; a compliance
  agent automatically checks the new language against regulatory requirements
  and flags issues before anyone else sees the change.
- **Style enforcement** — Any edit to a brand document triggers a brand-voice
  agent that ensures tone, terminology, and formatting stay consistent.
- **Cross-document sync** — A pricing table is updated in one deck; a hook
  propagates the change to every document that references those numbers.
- **Auto-summarization** — A new section is added to a report; a summarization
  agent updates the executive summary to reflect the new content.
- **Approval gating** — A finance section is modified; a hook notifies the CFO
  and blocks the file from being marked "final" until approval is received.

### How It Works

```
┌──────────────┐     event      ┌──────────────┐     task       ┌──────────────┐
│  Document    │ ─────────────▶ │  Hook        │ ─────────────▶ │  Agent       │
│  Change      │                │  Engine      │                │  Harness     │
└──────────────┘                └──────────────┘                └──────────────┘
       │                               │                               │
  user edits                    matches event                   runs the check
  or uploads                    against registered              or transformation,
  a document                    hooks, filters by               streams results
                                scope (doc, section,            via SSE
                                tag, user)
```

### Hook Definition

Hooks are registered per-organization and stored alongside documents in
Postgres. Each hook specifies:

| Field | Type | Description |
|-------|------|-------------|
| `id` | uuid | Unique hook identifier |
| `name` | string | Human-readable name (e.g., "Legal compliance check") |
| `event` | enum | Trigger event: `document.created`, `document.updated`, `section.created`, `section.updated`, `section.deleted` |
| `scope` | object | Filter conditions — which documents/sections this hook applies to (by tag, document ID, section type, or user role) |
| `agent_prompt` | text | The prompt passed to the agent harness when the hook fires |
| `action` | enum | What to do with the result: `comment`, `flag`, `block`, `transform` |
| `priority` | int | Execution order when multiple hooks match the same event |
| `enabled` | bool | Toggle without deleting |

### API

```
POST   /api/hooks                → Create a hook
GET    /api/hooks                → List hooks (filterable by event, scope)
GET    /api/hooks/{id}           → Get hook details
PUT    /api/hooks/{id}           → Update a hook
DELETE /api/hooks/{id}           → Delete a hook
GET    /api/hooks/{id}/history   → View past executions and results
```

#### Example: Create a legal compliance hook

```json
POST /api/hooks
{
  "name": "Legal clause review",
  "event": "section.updated",
  "scope": {
    "tags": ["legal", "contract"],
    "section_types": ["clause", "terms"]
  },
  "agent_prompt": "Review the updated section for compliance with GDPR, SOC 2, and internal legal guidelines. Flag any language that introduces liability risk or contradicts existing approved clauses.",
  "action": "flag",
  "priority": 1,
  "enabled": true
}
```

### Execution Flow

1. **Event emitted** — A user (or another agent) modifies a document or section.
   The change goes through the normal queue (Step 2 in file-operation-flow).
   After the task completes, the system emits a lifecycle event.

2. **Hook engine matches** — The hook engine checks all registered hooks against
   the event type and scope filters. Matching hooks are sorted by priority.

3. **Tasks enqueued** — Each matching hook creates a new task on the Redis queue
   with `taskType: "hook"`. These tasks reference the originating change so the
   agent has full context (diff, before/after content, metadata).

4. **Agent runs** — The task worker picks up the hook task and runs the agent
   harness with the hook's `agent_prompt` plus the change context.

5. **Action applied** — Based on the hook's `action` field:
   - `comment` — Agent output is added as a comment/annotation on the section
   - `flag` — The document is flagged for review with the agent's findings
   - `block` — The document is marked as blocked until a human resolves the flag
   - `transform` — The agent's output replaces or modifies the content directly

6. **Notification** — The user who made the change (and any watchers) receive
   an SSE event with the hook result.

```
event: hook_triggered  → Hook matched, agent starting
event: hook_delta      → Agent progress
event: hook_result     → Final output (comment, flag, or transform)
```

### Integration with Queue System

Hook tasks flow through the same Redis queue and document locking as regular
tasks. This means:

- Hook agents wait for the triggering edit to fully complete before running
- Multiple hooks on the same document execute sequentially (same doc lock)
- Hooks on different documents run in parallel
- Hook tasks appear in the standard task lifecycle (`QUEUED → RUNNING → COMPLETED`)
- Failed hooks follow the same retry logic with exponential backoff

### Scope Filters

Scopes let you target hooks precisely:

```json
{ "tags": ["legal"] }                          // Any doc tagged "legal"
{ "document_ids": ["abc-123"] }                // Specific document only
{ "section_types": ["financial", "pricing"] }  // Sections of these types
{ "user_roles": ["external", "contractor"] }   // Only edits by these roles
{ "tags": ["contract"], "user_roles": ["legal-team"] }  // Combine filters (AND)
```

### Hook Chaining

Hooks can trigger other hooks. For example:

1. Legal team edits a clause → **compliance hook** reviews the change
2. Compliance hook flags an issue → **notification hook** alerts the legal lead
3. Legal lead approves → **sync hook** propagates the approved clause to related docs

To prevent infinite loops, hooks have a max chain depth (default: 3) and each
hook execution carries a `trigger_chain` trace for debugging.
