---
sidebar_position: 4
title: Concurrency Model
---

# Concurrency Model

OfficePlane handles concurrent operations safely through document-level locking and a serialized task queue. Multiple users and agents can work simultaneously — the system ensures consistency.

## Same Document = Sequential

```
Agent A: "Add intro"     ─┐
                           ├──> Redis Queue ──> [Task 1: Add intro] → [Task 2: Fix typos]
Agent B: "Fix typos"     ─┘    + doc lock      (sequential, same doc)
```

Tasks targeting the same document are executed one at a time via the Redis document lock. This prevents:
- Partial file corruption from concurrent writes
- Race conditions between agents
- Lost updates

## Different Documents = Parallel

```
Agent C: "Edit doc X" ──> Redis Queue ──> [Task 3: Edit doc X]   ← runs in parallel
Agent D: "Edit doc Y" ──> Redis Queue ──> [Task 4: Edit doc Y]   ← runs in parallel
```

Tasks on different documents run concurrently across the worker pool (3 workers by default). Each worker independently acquires its document lock.

## Worker Pool

```
┌─────────────────────────────────────┐
│           Worker Pool (3)           │
│                                     │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐│
│  │Worker 1 │ │Worker 2 │ │Worker 3 ││
│  │ doc: A  │ │ doc: B  │ │  idle   ││
│  └─────────┘ └─────────┘ └─────────┘│
└─────────────────────────────────────┘
           ▲           ▲           ▲
           │           │           │
    ┌──────┴───────────┴───────────┴──────┐
    │          Redis Task Queue            │
    │  [task5] [task4] [task3] [task2]     │
    └─────────────────────────────────────┘
```

Workers use `BRPOP` to block-wait on the queue — zero polling overhead. When a task arrives, the next idle worker picks it up immediately.

## Lock Contention

When a worker picks up a task but can't acquire the document lock (another worker holds it):

1. The task is **re-queued** at the back of the Redis list
2. The worker moves on to the next available task
3. No CPU is wasted spinning

This means high-priority tasks for unlocked documents can leapfrog contended tasks.

## Agent Teams Concurrency

Agent teams add another layer of parallelism. Within a team:

```
Team Lead
├── Decomposes prompt into N sub-tasks
├── Pushes tasks to Redis shared list
└── Spawns N teammate agents

Teammates (parallel)
├── Agent 1: Claims task A, executes
├── Agent 2: Claims task B, executes
└── Agent 3: Claims task C, executes
```

- Task claiming is atomic (Redis `LPOP`)
- Dependencies between tasks are tracked in Redis sets
- Teammates communicate via Redis pub/sub mailboxes
