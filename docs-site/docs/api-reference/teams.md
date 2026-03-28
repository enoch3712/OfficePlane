---
sidebar_position: 6
title: Teams
---

# Teams API

Orchestrate multi-agent teams for complex document tasks.

## Start Team

```bash
POST /api/teams
Content-Type: application/json
```

```json
{
  "prompt": "Create a comprehensive market analysis report",
  "teammates": [
    { "role": "researcher", "focus": "competitor analysis" },
    { "role": "analyst", "focus": "market sizing and pricing" },
    { "role": "writer", "focus": "report compilation and formatting" }
  ]
}
```

**Response (202 Accepted):**

```json
{
  "team_id": "team-abc-123",
  "status": "started",
  "num_teammates": 3,
  "stream_url": "/api/teams/team-abc-123/stream"
}
```

## Stream Events (SSE)

```bash
GET /api/teams/{team_id}/stream
Accept: text/event-stream
```

```
event: team_started
data: {"team_id": "team-abc-123", "num_teammates": 3, "num_tasks": 6}

event: task_claimed
data: {"teammate": "researcher", "task_id": "t1", "description": "Identify top 5 competitors"}

event: task_completed
data: {"teammate": "researcher", "task_id": "t1", "duration_ms": 12000}

event: task_claimed
data: {"teammate": "writer", "task_id": "t5", "description": "Compile final report"}

event: team_completed
data: {"team_id": "team-abc-123", "document_id": "doc-xyz", "total_duration_ms": 38000}
```

## Get Team Status

```bash
GET /api/teams/{team_id}
```

```json
{
  "team_id": "team-abc-123",
  "status": "completed",
  "document_id": "doc-xyz",
  "tasks_completed": 6,
  "tasks_total": 6,
  "total_duration_ms": 38000,
  "teammates": [
    { "role": "researcher", "tasks_done": 2, "status": "done" },
    { "role": "analyst", "tasks_done": 2, "status": "done" },
    { "role": "writer", "tasks_done": 2, "status": "done" }
  ]
}
```

### Status Values

| Status | Description |
|--------|-------------|
| `started` | Team initialized, tasks being distributed |
| `running` | Teammates actively working |
| `completed` | All tasks done, result available |
| `failed` | One or more critical tasks failed |
| `cancelled` | Cancelled by user |

## Cancel Team

```bash
DELETE /api/teams/{team_id}
```

Cancels all running teammate tasks and stops the team.
