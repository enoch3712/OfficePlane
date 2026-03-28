---
sidebar_position: 5
title: Document Hooks
---

# Document Hooks

Hooks let you attach automated agent actions to document lifecycle events. When a document is created, edited, or has a section changed, OfficePlane can automatically trigger agents to review, validate, or transform the content — no manual intervention required.

## Use Cases

| Scenario | Hook Event | Action |
|----------|-----------|--------|
| **Legal compliance** | `section.updated` on tagged "legal" docs | Agent reviews language against GDPR/SOC 2 requirements |
| **Style enforcement** | `document.updated` on brand documents | Brand-voice agent checks tone and terminology |
| **Cross-document sync** | `section.updated` on pricing sections | Propagate changes to all referencing documents |
| **Auto-summarization** | `section.created` on reports | Summarization agent updates the executive summary |
| **Approval gating** | `section.updated` on finance sections | Block document from "final" status until CFO approves |

## How It Works

```
┌──────────────┐     event      ┌──────────────┐     task       ┌──────────────┐
│  Document    │ ──────────────>│  Hook        │ ──────────────>│  Agent       │
│  Change      │                │  Engine      │                │  Harness     │
└──────────────┘                └──────────────┘                └──────────────┘
       │                               │                               │
  User or agent                 Match event against            Run the check or
  edits a document              registered hooks,              transformation,
                                filter by scope                stream via SSE
```

### Execution Flow

1. **Event emitted** — A user or agent modifies a document. After the task completes, a lifecycle event fires.
2. **Hook engine matches** — Registered hooks are checked against the event type and scope filters. Matching hooks are sorted by priority.
3. **Tasks enqueued** — Each matching hook creates a `taskType: "hook"` task on the Redis queue, referencing the originating change (diff, before/after, metadata).
4. **Agent runs** — The worker runs the agent harness with the hook's prompt plus the change context.
5. **Action applied** — Based on the hook's action type:

| Action | Behavior |
|--------|----------|
| `comment` | Agent output is added as an annotation on the section |
| `flag` | Document is flagged for review with the agent's findings |
| `block` | Document is blocked until a human resolves the flag |
| `transform` | Agent output replaces or modifies the content directly |

6. **Notification** — The user and watchers receive an SSE event with the result.

## Hook Definition

| Field | Type | Description |
|-------|------|-------------|
| `id` | uuid | Unique identifier |
| `name` | string | Human-readable name |
| `event` | enum | Trigger: `document.created`, `document.updated`, `section.created`, `section.updated`, `section.deleted` |
| `scope` | object | Filter conditions (by tag, document ID, section type, user role) |
| `agent_prompt` | text | Prompt for the agent harness |
| `action` | enum | `comment`, `flag`, `block`, `transform` |
| `priority` | int | Execution order when multiple hooks match |
| `enabled` | bool | Toggle without deleting |

## API

```bash
# Create a hook
POST /api/hooks
{
  "name": "Legal clause review",
  "event": "section.updated",
  "scope": {
    "tags": ["legal", "contract"],
    "section_types": ["clause", "terms"]
  },
  "agent_prompt": "Review the updated section for compliance with GDPR, SOC 2, and internal legal guidelines. Flag any language that introduces liability risk.",
  "action": "flag",
  "priority": 1,
  "enabled": true
}

# List hooks
GET /api/hooks

# Get hook details
GET /api/hooks/{id}

# Update a hook
PUT /api/hooks/{id}

# Delete a hook
DELETE /api/hooks/{id}

# View execution history
GET /api/hooks/{id}/history
```

## Scope Filters

Target hooks precisely using scope objects:

```json
// Any document tagged "legal"
{ "tags": ["legal"] }

// Specific document only
{ "document_ids": ["abc-123"] }

// Sections of specific types
{ "section_types": ["financial", "pricing"] }

// Only edits by certain roles
{ "user_roles": ["external", "contractor"] }

// Combine filters (AND logic)
{ "tags": ["contract"], "user_roles": ["legal-team"] }
```

## SSE Events

```
event: hook_triggered   → Hook matched, agent starting
event: hook_delta       → Agent progress
event: hook_result      → Final output (comment, flag, or transform)
```

## Hook Chaining

Hooks can trigger other hooks:

1. Legal team edits a clause → **compliance hook** reviews the change
2. Compliance hook flags an issue → **notification hook** alerts the legal lead
3. Legal lead approves → **sync hook** propagates to related docs

To prevent infinite loops, hooks have a max chain depth (default: 3) and each execution carries a `trigger_chain` trace.

## Queue Integration

Hook tasks flow through the same Redis queue as regular tasks:

- Wait for the triggering edit to fully complete before running
- Same document lock — multiple hooks on one doc execute sequentially
- Different documents — hooks run in parallel
- Same retry logic with exponential backoff
- Appear in standard task lifecycle (`QUEUED → RUNNING → COMPLETED`)
