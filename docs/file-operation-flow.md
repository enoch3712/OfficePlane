# OfficePlane — File Operation Flow

## Overview

Every file mutation in OfficePlane follows a 5-step pipeline. This ensures
atomic edits, prevents conflicts between concurrent agents/requests, and
guarantees the file is always in a consistent state.

```
┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ 1. Open      │───▶│ 2. Queue     │───▶│ 3. Change    │───▶│ 4. Pretty    │───▶│ 5. Get       │
│    Instance  │    │    (atomic)  │    │    (harness) │    │    (format)  │    │    File      │
└──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

---

## Step 1 — Start Instance (open the file)

An **instance** represents an open file session. Opening an instance:
- Loads the document from the database
- Acquires exclusive access to the underlying file
- Marks the document as `IN_USE` so other operations know it's active
- Starts the backing driver (LibreOffice) if format conversion is needed

```
POST /api/instances
{ "documentId": "<uuid>" }

→ Instance { id, state: OPEN, documentId }
```

**Rules:**
- One active instance per document at a time (enforced by the queue, see step 2)
- Instance must be explicitly closed or will time out
- All subsequent operations reference the instance ID

---

## Step 2 — Queue System (atomic control)

The **task queue** serializes all mutations on a given document. When a change
is requested, it goes through the queue — never directly to the file.

```
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
┌─────────────┐      push (LPUSH/RPUSH)      ┌───────────────┐
│  API Server  │ ──────────────────────────▶  │  Redis 7      │
│  (producer)  │                              │  (queue +     │
└─────────────┘                               │   locks +     │
                                              │   pub/sub)    │
┌─────────────┐      pop (BRPOP)              └───────────────┘
│  Workers     │ ◀──────────────────────────
│  (consumers) │
└─────────────┘
```

- **Redis list** (`officeplane:tasks`) — tasks are pushed when enqueued,
  workers BRPOP to block-wait (instant wakeup, no polling).
- **Redis SETNX** (`officeplane:doclock:{doc_id}`) — document-level lock.
  A worker must acquire the lock before mutating a document. If another task
  already holds it, the new task goes back on the queue.
- **Postgres** remains the source of truth for task state, payloads, retries.
  Redis is the dispatch layer.

### Atomicity guarantees

- Tasks targeting the same `documentId` are executed sequentially (Redis lock)
- Multiple agents/users can submit tasks concurrently — the queue orders them
- Each task either completes fully or rolls back (no partial file corruption)
- Retry logic with exponential backoff if a transient failure occurs
- Lock auto-expires after 10 min (crashed worker can't hold forever)

### Task lifecycle

```
QUEUED → RUNNING → COMPLETED
                 → FAILED → RETRYING → RUNNING → ...
```

### Graceful degradation

If Redis is unavailable, the system falls back to Postgres polling (1s interval)
and skips document locking. This matches the pre-Redis behavior.

---

## Step 3 — Change (agent harness)

The actual file modification is performed by the **agent harness** — an
autonomous AI agent with tool access (bash, file I/O, Node.js, Python).

This replaces the old plan → execute → verify pattern. Instead:
- The task worker hands the prompt + workspace to the agent harness
- The agent reads the current file, decides what to change, and makes the edits
- It uses real tools (python-docx, pptxgenjs, etc.) to modify the file directly
- Changes are streamed back via SSE so the user sees progress in real time

```
Agent Harness
├── Reads current document from workspace
├── Analyzes what changes are needed
├── Executes changes using tools:
│   ├── python-docx (Word editing)
│   ├── pptxgenjs (PowerPoint creation/editing)
│   ├── python-pptx (PowerPoint manipulation)
│   └── custom scripts as needed
├── Writes modified file back to workspace
└── Reports completion via SSE stream
```

### SSE events (via Redis pub/sub)

The agent publishes events to `officeplane:sse:{job_id}`. The HTTP handler
subscribes to that channel. This decouples worker from API server.

```
event: start      → Agent begins working
event: delta      → Agent thinking/planning text
event: tool_call  → Agent invokes a tool (e.g., bash command)
event: tool_result→ Tool output
event: stop       → Done (includes document_id)
```

---

## Step 4 — Pretty (format/beautify)

After changes are applied, an optional **pretty** step normalizes the file:

- **DOCX/PPTX**: Normalize styles, fix heading hierarchy, consistent fonts/sizes,
  remove duplicate whitespace, ensure proper page breaks
- **HTML**: Format/indent markup, validate structure
- **General**: Ensure metadata.json is up to date with current structure

```python
pretty(workspace_path, file_format)
```

**What pretty does:**
- Reads the modified file from the workspace
- Applies format-specific normalization rules
- Fixes common issues (orphaned styles, broken references, inconsistent spacing)
- Writes the cleaned file back
- This is idempotent — running it twice produces the same result

**When pretty is applied:**
- Automatically after every agent harness change (step 3)
- Can be skipped via task option `"skip_pretty": true` for raw output
- Can be run standalone: `POST /api/tasks { "taskType": "pretty", ... }`

---

## Step 5 — Get File

The final file is stored in the document store and can be retrieved:

```
GET /api/documents/{id}/download?format=original   → Original file bytes
GET /api/documents/{id}/download?format=docx        → Regenerated DOCX
GET /api/documents/{id}/download?format=markdown     → Markdown export
GET /api/documents/{id}/download?format=pdf          → PDF via LibreOffice
```

The file is also accessible through the document hierarchy API:
```
GET /api/documents/{id}          → Full structure (chapters/sections/pages)
GET /api/documents/{id}/outline  → Lightweight TOC view
```

---

## Complete Flow Example

```
User: "Add a risk analysis section to my pitch deck"

1. POST /api/instances { documentId: "abc" }
   → Instance opened, document locked

2. POST /api/generate (or POST /api/tasks)
   {
     "prompt": "Add a risk analysis section after the market analysis...",
     "documentId": "abc",
     "instanceId": "inst_123"
   }
   → Task pushed to Redis, worker wakes up immediately
   → Worker acquires doc lock (Redis SETNX), no other task can touch doc "abc"

3. Agent harness runs:
   → Reads current document structure
   → Identifies where market analysis section ends
   → Creates new section with risk analysis content
   → Writes modified file
   → SSE events streamed via Redis pub/sub

4. pretty() runs:
   → Normalizes heading levels
   → Ensures consistent font usage
   → Fixes any style inconsistencies

5. GET /api/documents/abc/download?format=pptx
   → Returns the updated file

6. POST /api/instances/inst_123/close
   → Instance closed, document lock released
```

---

## Concurrency Model

```
Agent A: "Add intro"     ─┐
                           ├──▶ Redis Queue ──▶ [Task 1: Add intro] → [Task 2: Fix typos]
Agent B: "Fix typos"     ─┘    + doc lock      (sequential on same doc)

Agent C: "Edit other doc" ──▶ Redis Queue ──▶ [Task 3: Edit other doc]
                                               (parallel — different doc)
```

Tasks on the **same document** are serialized via Redis document lock.
Tasks on **different documents** run in parallel across the worker pool.

---

## Infrastructure

| Service | Image | Port | Purpose |
|---------|-------|------|---------|
| db | pgvector/pgvector:pg16 | 5433 | Postgres — documents, task state, source of truth |
| redis | redis:7-alpine | 6379 | Task dispatch, document locks, SSE pub/sub |
| api | officeplane (custom) | 8001 | FastAPI + task workers |
| ui | next.js (custom) | 3000 | Frontend |
