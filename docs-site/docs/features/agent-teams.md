---
sidebar_position: 4
title: Agent Teams
---

# Agent Teams

Agent teams let you decompose complex document tasks across multiple AI agents running in parallel. A team lead orchestrates the work, while teammates claim and execute sub-tasks concurrently.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  Team Lead                       │
│                                                  │
│  1. Receives prompt                              │
│  2. Decomposes into sub-tasks                    │
│  3. Pushes to shared task list (Redis)           │
│  4. Spawns teammates                             │
│  5. Waits for all completions                    │
│  6. Synthesizes final result                     │
└────────────────────┬────────────────────────────┘
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
   ┌────────────┐ ┌────────────┐ ┌────────────┐
   │ Teammate 1 │ │ Teammate 2 │ │ Teammate 3 │
   │            │ │            │ │            │
   │ Claim task │ │ Claim task │ │ Claim task │
   │ Execute    │ │ Execute    │ │ Execute    │
   │ Report     │ │ Report     │ │ Report     │
   └────────────┘ └────────────┘ └────────────┘
```

## How Teammates Work

Each teammate runs an autonomous loop:

```
while tasks_remaining:
    task = claim_task()          # Redis LPOP (atomic)
    if task.dependencies_met():  # Check Redis set
        result = execute(task)
        report_completion(result) # Redis pub/sub
        broadcast(result)         # Mailbox for other teammates
    else:
        release_task(task)        # Put back for later
```

### Task Claiming

- Teammates claim tasks atomically via Redis `LPOP`
- No two teammates can claim the same task
- If a task's dependencies aren't met, it's released back

### Dependencies

Tasks can depend on other tasks:

```json
{
  "task_id": "write-conclusion",
  "depends_on": ["research-market", "analyze-competitors"],
  "prompt": "Write a conclusion based on the research and analysis"
}
```

Dependencies are tracked in Redis sets. A task only runs when all its dependencies have completed.

### Communication

Teammates communicate via Redis pub/sub **mailboxes**:

```
Teammate 1 finishes "research-market"
  → Broadcasts result to officeplane:team:{id}:broadcast
  → All teammates receive it
  → Teammate 3 sees its dependency is now met
  → Teammate 3 proceeds with "write-conclusion"
```

## API

### Start a Team

```bash
POST /api/teams
{
  "prompt": "Create a comprehensive market analysis report with competitor research, pricing analysis, and growth projections",
  "teammates": [
    { "role": "researcher", "focus": "competitor analysis" },
    { "role": "analyst", "focus": "pricing and market data" },
    { "role": "writer", "focus": "report compilation" }
  ]
}
```

### Stream Events

```bash
GET /api/teams/{team_id}/stream
```

```
event: team_started
data: {"team_id": "team-123", "num_teammates": 3}

event: task_claimed
data: {"teammate": "researcher", "task": "analyze top 5 competitors"}

event: task_completed
data: {"teammate": "researcher", "task": "analyze top 5 competitors", "duration_ms": 12000}

event: task_claimed
data: {"teammate": "writer", "task": "compile final report"}

event: team_completed
data: {"team_id": "team-123", "document_id": "doc-456", "total_duration_ms": 35000}
```

### Check Status

```bash
GET /api/teams/{team_id}
```

```json
{
  "team_id": "team-123",
  "status": "completed",
  "document_id": "doc-456",
  "tasks_completed": 5,
  "tasks_total": 5,
  "teammates": [
    { "role": "researcher", "tasks_done": 2 },
    { "role": "analyst", "tasks_done": 2 },
    { "role": "writer", "tasks_done": 1 }
  ]
}
```

## Redis Infrastructure

All team coordination happens in Redis:

| Key Pattern | Type | Purpose |
|-------------|------|---------|
| `officeplane:team:{id}:tasks` | Hash | Task definitions |
| `officeplane:team:{id}:queue` | List | Available tasks (LPOP) |
| `officeplane:team:{id}:deps:{task_id}` | Set | Dependencies |
| `officeplane:team:{id}:broadcast` | Pub/Sub | Team-wide messages |
| `officeplane:team:{id}:mailbox:{agent}` | Pub/Sub | Direct messages |
