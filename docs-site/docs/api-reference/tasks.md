---
sidebar_position: 4
title: Tasks
---

# Tasks API

Create, monitor, cancel, and retry tasks in the queue.

## Create Task

```bash
POST /api/tasks
Content-Type: application/json
```

```json
{
  "taskType": "file_change",
  "documentId": "doc-abc-123",
  "instanceId": "inst-xyz-789",
  "priority": "NORMAL",
  "payload": {
    "prompt": "Rewrite the introduction paragraph to be more concise"
  }
}
```

**Response:**

```json
{
  "id": "task-456",
  "taskType": "file_change",
  "state": "QUEUED",
  "priority": "NORMAL",
  "documentId": "doc-abc-123",
  "createdAt": "2026-03-18T10:30:00Z"
}
```

## List Tasks

```bash
GET /api/tasks
GET /api/tasks?state=RUNNING
GET /api/tasks?documentId=doc-abc-123
GET /api/tasks?priority=HIGH
```

**Response:**

```json
[
  {
    "id": "task-456",
    "taskType": "file_change",
    "state": "RUNNING",
    "priority": "NORMAL",
    "documentId": "doc-abc-123",
    "workerId": "worker-1",
    "startedAt": "2026-03-18T10:30:02Z",
    "retries": 0,
    "maxRetries": 3
  }
]
```

## Cancel Task

```bash
POST /api/tasks/{id}/cancel
```

**Response:**

```json
{
  "id": "task-456",
  "state": "CANCELLED",
  "cancelledAt": "2026-03-18T10:31:00Z"
}
```

## Retry Task

Retry a failed task. Resets the state to `QUEUED`.

```bash
POST /api/tasks/{id}/retry
```

## Task Types

| Type | Description |
|------|-------------|
| `file_change` | Modify a document via agent harness |
| `content_generate` | Generate new content |
| `hook` | Automated hook execution |
| `pretty` | Format/normalize a document |
| `batch_edit` | Parent task with child edits |

## Priority Levels

| Priority | Value | Use Case |
|----------|-------|----------|
| `CRITICAL` | 4 | System operations |
| `HIGH` | 3 | User-initiated actions |
| `NORMAL` | 2 | Standard operations |
| `LOW` | 1 | Background tasks |
