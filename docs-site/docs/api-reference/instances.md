---
sidebar_position: 3
title: Instances
---

# Instances API

Instances represent open document sessions. They provide exclusive access to a document and manage the document driver lifecycle.

## Open Instance

```bash
POST /api/instances
Content-Type: application/json
```

```json
{
  "documentId": "doc-abc-123"
}
```

**Response:**

```json
{
  "id": "inst-xyz-789",
  "documentId": "doc-abc-123",
  "state": "OPEN",
  "driverType": "libreoffice",
  "createdAt": "2026-03-18T10:30:00Z"
}
```

:::info One Instance Per Document
Only one instance can be open per document at a time. Attempting to open a second instance for the same document will return a 409 Conflict.
:::

## List Instances

```bash
GET /api/instances
```

**Response:**

```json
[
  {
    "id": "inst-xyz-789",
    "documentId": "doc-abc-123",
    "state": "OPEN",
    "driverType": "libreoffice",
    "processId": 12345,
    "memoryMb": 48.2,
    "cpuPercent": 2.1,
    "heartbeatAt": "2026-03-18T10:30:05Z"
  }
]
```

## Get Instance

```bash
GET /api/instances/{id}
```

## Close Instance

Gracefully close an instance and release all locks.

```bash
POST /api/instances/{id}/close
```

**Response:**

```json
{
  "id": "inst-xyz-789",
  "state": "CLOSED",
  "closedAt": "2026-03-18T10:35:00Z"
}
```

## Delete Instance

Force-delete an instance (use when close fails).

```bash
DELETE /api/instances/{id}
```

## Instance States

```
OPENING → OPEN → IDLE → IN_USE → CLOSING → CLOSED
                                          → ERROR
                                          → CRASHED
```

| State | Description |
|-------|-------------|
| `OPENING` | Driver starting up |
| `OPEN` | Ready to accept tasks |
| `IDLE` | Open but no active task |
| `IN_USE` | Currently executing a task |
| `CLOSING` | Shutting down gracefully |
| `CLOSED` | Fully closed, locks released |
| `ERROR` | Failed during operation |
| `CRASHED` | Heartbeat lost, auto-recovery |

Instances have a **5-second heartbeat**. If missed, the instance transitions to `CRASHED` and all locks are released.
