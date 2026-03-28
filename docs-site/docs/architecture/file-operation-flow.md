---
sidebar_position: 2
title: File Operation Flow
---

# File Operation Flow

Every file mutation in OfficePlane follows a 5-step pipeline. This ensures atomic edits, prevents conflicts between concurrent agents/requests, and guarantees the file is always in a consistent state.

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ 1. Open      │───>│ 2. Queue     │───>│ 3. Change    │───>│ 4. Pretty    │───>│ 5. Get       │
│    Instance  │    │    (atomic)  │    │    (harness) │    │    (format)  │    │    File      │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

## Step 1 — Open Instance

An **instance** represents an open file session. Opening an instance:
- Loads the document from the database
- Acquires exclusive access to the underlying file
- Marks the document as `IN_USE`
- Starts the backing driver (LibreOffice) if format conversion is needed

```bash
POST /api/instances
{ "documentId": "<uuid>" }

# Returns: Instance { id, state: OPEN, documentId }
```

**Rules:**
- One active instance per document at a time (enforced by the queue)
- Instance must be explicitly closed or will time out
- All subsequent operations reference the instance ID

### Instance Lifecycle

```
OPENING → OPEN → IDLE → IN_USE → CLOSING → CLOSED
                                          → ERROR
                                          → CRASHED
```

Instances have a 5-second heartbeat monitor. If the heartbeat is missed, the instance transitions to `CRASHED` and releases its locks.

## Step 2 — Queue (Atomic Control)

The **task queue** serializes all mutations on a given document. Changes go through the queue — never directly to the file.

```bash
POST /api/tasks
{
  "taskType": "file_change",
  "documentId": "<uuid>",
  "instanceId": "<uuid>",
  "payload": { "prompt": "Add an executive summary section..." }
}
```

### Infrastructure

```
┌─────────────┐      LPUSH/RPUSH       ┌───────────────┐
│  API Server  │ ─────────────────────> │  Redis 7      │
│  (producer)  │                        │  queue +      │
└─────────────┘                         │  locks +      │
                                        │  pub/sub      │
┌─────────────┐      BRPOP             └───────────────┘
│  Workers     │ <─────────────────────
│  (consumers) │
└─────────────┘
```

- **Redis list** (`officeplane:tasks`) — tasks pushed, workers BRPOP (instant wakeup)
- **Redis SETNX** (`officeplane:doclock:{doc_id}`) — document-level lock
- **PostgreSQL** — source of truth for task state, payloads, retries

### Atomicity Guarantees

- Tasks targeting the same `documentId` execute sequentially (Redis lock)
- Multiple agents/users can submit tasks concurrently — the queue orders them
- Each task either completes fully or rolls back (no partial file corruption)
- Lock auto-expires after 10 min (crashed workers can't hold forever)

## Step 3 — Change (Agent Harness)

The agent harness performs the actual file modification:

```
Agent Harness
├── Reads current document from workspace
├── Analyzes what changes are needed
├── Executes changes using tools:
│   ├── python-docx (Word editing)
│   ├── pptxgenjs (PowerPoint creation)
│   ├── python-pptx (PowerPoint manipulation)
│   └── custom scripts as needed
├── Writes modified file back to workspace
└── Reports completion via SSE stream
```

### SSE Events (via Redis pub/sub)

The agent publishes to `officeplane:sse:{job_id}`. The HTTP handler subscribes and streams to the client:

```
event: start        → Agent begins working
event: delta        → Agent thinking/planning text
event: tool_call    → Agent invokes a tool
event: tool_result  → Tool output
event: stop         → Done (includes document_id)
```

## Step 4 — Pretty (Format/Beautify)

After changes are applied, an optional normalization step runs:

- **DOCX/PPTX** — Normalize styles, fix heading hierarchy, consistent fonts/sizes
- **HTML** — Format/indent markup, validate structure
- **General** — Ensure metadata is up to date

```python
pretty(workspace_path, file_format)
```

This is idempotent — running it twice produces the same result. It can be skipped via `"skip_pretty": true` on the task.

## Step 5 — Get File

Download the final file in any supported format:

```bash
GET /api/documents/{id}/download?format=original    # Original bytes
GET /api/documents/{id}/download?format=docx         # Regenerated DOCX
GET /api/documents/{id}/download?format=markdown      # Markdown export
GET /api/documents/{id}/download?format=pdf           # PDF via LibreOffice
```

## Complete Example

```
User: "Add a risk analysis section to my pitch deck"

1. POST /api/instances { documentId: "abc" }
   → Instance opened, document locked

2. POST /api/tasks { prompt: "Add risk analysis section...", documentId: "abc" }
   → Task pushed to Redis, worker wakes up immediately
   → Worker acquires doc lock via SETNX

3. Agent harness runs:
   → Reads current document structure
   → Identifies where to insert new section
   → Creates risk analysis content
   → Writes modified file
   → SSE events streamed to client

4. pretty() runs:
   → Normalizes heading levels
   → Ensures consistent font usage

5. GET /api/documents/abc/download?format=pptx
   → Returns the updated file
```
