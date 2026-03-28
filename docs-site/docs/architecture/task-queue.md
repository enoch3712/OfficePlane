---
sidebar_position: 3
title: Task Queue
---

# Task Queue

The task queue is the backbone of OfficePlane's mutation system. It serializes document edits, manages retries, and ensures no two operations corrupt the same file.

## How It Works

```
┌─────────────┐     LPUSH      ┌───────────────┐     BRPOP      ┌─────────────┐
│  API Server  │ ─────────────> │  Redis List    │ <──────────── │  Workers     │
│  (producer)  │                │  officeplane:  │               │  (consumers) │
│              │                │  tasks         │               │              │
└─────────────┘                └───────────────┘               └──────┬──────┘
                                                                       │
                                                               ┌──────▼──────┐
                                                               │  PostgreSQL  │
                                                               │  (state +    │
                                                               │   payloads)  │
                                                               └─────────────┘
```

- **Redis** is the dispatch layer — tasks are pushed to a list, workers BRPOP to block-wait (instant wakeup, no polling)
- **PostgreSQL** is the source of truth for task state, payloads, results, and retry counts
- **3 background workers** process tasks concurrently (configurable)

## Task Lifecycle

```
QUEUED → RUNNING → COMPLETED
                 → FAILED → RETRYING → RUNNING → ...
                 → CANCELLED
                 → TIMEOUT
```

| State | Description |
|-------|-------------|
| `QUEUED` | Waiting in Redis list for a worker |
| `RUNNING` | Claimed by a worker, actively executing |
| `COMPLETED` | Successfully finished |
| `FAILED` | Execution error, may be retried |
| `RETRYING` | Scheduled for retry after backoff |
| `CANCELLED` | Cancelled by user or system |
| `TIMEOUT` | Exceeded execution time limit |

## Document Locking

Before a worker can mutate a document, it must acquire the document lock:

```
Redis SETNX officeplane:doclock:{doc_id}  →  acquired (true) or blocked (false)
```

- **SETNX** — atomic set-if-not-exists
- **TTL** — 10 minute auto-expiry (prevents deadlocks from crashed workers)
- **Lua script** — atomic release (only the holder can release)
- If a task can't acquire the lock, it goes back on the queue

This means tasks on the **same document** are serialized, while tasks on **different documents** run in parallel.

## Priority Levels

| Priority | Use Case |
|----------|----------|
| `CRITICAL` | System operations, recovery tasks |
| `HIGH` | User-initiated actions |
| `NORMAL` | Standard operations (default) |
| `LOW` | Background maintenance, optimizations |

## Retry Logic

Failed tasks are retried with exponential backoff:

```
Attempt 1 → immediate
Attempt 2 → 5s delay
Attempt 3 → 25s delay
Attempt 4 → 125s delay
...
```

Each task has a `maxRetries` field (default: 3). After exhausting retries, the task is permanently `FAILED`.

## Parent-Child Tasks

Tasks can have parent-child relationships for complex workflows:

```json
{
  "taskType": "batch_edit",
  "documentId": "abc",
  "children": [
    { "taskType": "add_section", "payload": { ... } },
    { "taskType": "write_page", "payload": { ... } }
  ]
}
```

Child tasks execute in order, and the parent task completes only when all children finish.

## Graceful Degradation

If Redis is unavailable, the system falls back to:
- **PostgreSQL polling** (1-second interval) for task dispatch
- **No document locking** (matches pre-Redis behavior)

This ensures the system remains operational even without Redis, at the cost of reduced performance and no atomicity guarantees.

## Monitoring

```bash
# View task states
curl http://localhost:8001/api/tasks

# Check specific task
curl http://localhost:8001/api/tasks/{id}

# Cancel a task
curl -X POST http://localhost:8001/api/tasks/{id}/cancel

# Retry a failed task
curl -X POST http://localhost:8001/api/tasks/{id}/retry
```
