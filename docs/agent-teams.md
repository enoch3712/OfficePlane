# Agent Teams

## Pattern

```
┌─────────────────────────────────────────────────────────────────────┐
│                     Main Agent (Team Lead)                          │
│                                                                     │
│  1. Receives user prompt                                            │
│  2. Decomposes into tasks (via LLM)                                 │
│  3. Populates shared task list                                      │
│  4. Waits for teammates to finish                                   │
│  5. Synthesizes results                                             │
└──────────────────────────┬──────────────────────────────────────────┘
                           │
                  Spawn Team & Assign Tasks
                           │
              ┌────────────▼────────────────┐
              │     Shared Task List         │
              │     (Redis hash + list)      │
              │                              │
              │  task_1: pending             │
              │  task_2: pending             │
              │  task_3: depends_on:[task_1] │
              └──┬──────────┬──────────┬────┘
                 │          │          │
          Claim  │   Claim  │   Claim  │
                 │          │          │
         ┌───────▼──┐ ┌────▼─────┐ ┌──▼────────┐
         │Teammate A│ │Teammate B│ │Teammate C │
         │researcher│ │designer  │ │writer     │
         └───┬──────┘ └────┬─────┘ └──┬────────┘
             │             │           │
             │◄── Communicate ────────►│
             │    (Redis pub/sub)      │
             │             │           │
          Work          Work        Work
```

**Key difference from subagents:** teammates share a task list, claim work
atomically, and message each other directly. Subagents only report back
to the parent.

---

## Infrastructure

All coordination runs through Redis (already in our compose):

| Mechanism | Redis primitive | Key pattern |
|-----------|----------------|-------------|
| Shared task list | Hash + List | `officeplane:team:{id}:tasks`, `officeplane:team:{id}:available` |
| Task claiming | LPOP (atomic) | Single pop from available list — no double-claiming |
| Dependencies | Set | `officeplane:team:{id}:completed` — unblocks dependents |
| Mailbox (direct) | Pub/Sub | `officeplane:team:{id}:mail:{agent_id}` |
| Broadcast | Pub/Sub | `officeplane:team:{id}:broadcast` |
| SSE streaming | Pub/Sub | `officeplane:sse:{team_id}` |

No new infrastructure needed — Redis handles everything.

---

## API

### `POST /api/teams` — Start a team

```json
{
  "prompt": "Create a pitch deck about AI in healthcare",
  "teammates": [
    { "role": "researcher", "prompt": "Research the topic thoroughly" },
    { "role": "designer",   "prompt": "Design the slide structure and layout" },
    { "role": "writer",     "prompt": "Write compelling slide content" }
  ],
  "model": "gpt-4o",
  "document_id": "optional-uuid"
}
```

Response (202):
```json
{
  "team_id": "team_a1b2c3d4e5f6",
  "status": "running",
  "stream_url": "/api/teams/team_a1b2c3d4e5f6/stream",
  "teammates": ["researcher", "designer", "writer"]
}
```

### `GET /api/teams/{id}/stream` — SSE events

```
event: decomposing
data: {"agent_id": "lead", "prompt": "Create a pitch deck..."}

event: tasks_created
data: {"agent_id": "lead", "count": 8, "tasks": [...]}

event: teammates_started
data: {"agent_id": "lead", "teammates": [{"id": "researcher_0", "role": "researcher"}, ...]}

event: task_claimed
data: {"agent_id": "researcher_0", "task_id": "task_1", "title": "Research market size"}

event: task_completed
data: {"agent_id": "researcher_0", "task_id": "task_1", "result": "..."}

event: synthesizing
data: {"agent_id": "lead"}

event: team_completed
data: {"agent_id": "lead", "duration_ms": 45000, "summary": {"completed": 8, "failed": 0}}
```

### `GET /api/teams/{id}` — Status + result
### `DELETE /api/teams/{id}` — Cancel

---

## How it works

### 1. Decomposition

The team lead uses an LLM to break the user's prompt into a list of tasks
with optional dependencies:

```json
{
  "tasks": [
    {"id": "task_1", "title": "Research market", "description": "...", "depends_on": []},
    {"id": "task_2", "title": "Research competitors", "description": "...", "depends_on": []},
    {"id": "task_3", "title": "Draft slide outline", "description": "...", "depends_on": ["task_1", "task_2"]}
  ]
}
```

Tasks without dependencies go straight to the available list.
Tasks with dependencies wait until all deps are completed.

### 2. Claiming

Teammates run a loop: `claim_task()` → `execute()` → `complete_task()` → repeat.

`claim_task()` uses Redis LPOP — atomic, no locks needed, no double-claiming.
If a task's dependencies aren't met, it goes back on the queue.

### 3. Communication

Teammates receive messages from others via their mailbox (Redis pub/sub).
When a teammate completes a task, it broadcasts the result.
Other teammates see this in their next execution context — they can build
on each other's findings.

### 4. Synthesis

When all tasks are done, the lead collects all completed results and asks
the LLM to synthesize them into a single coherent output.

---

## Module structure

```
src/officeplane/agent_team/
├── __init__.py
├── team.py          # AgentTeam: lead + orchestration + synthesis
├── teammate.py      # Teammate: claim → execute → complete loop
├── shared_tasks.py  # SharedTaskList: Redis-backed task list with deps
└── mailbox.py       # Mailbox: Redis pub/sub messaging

src/officeplane/api/team_routes.py  # POST/GET/DELETE /api/teams
```

---

## Examples

### Parallel document editing

```json
{
  "prompt": "Improve this pitch deck: fix grammar, add market data, redesign layout",
  "teammates": [
    { "role": "editor", "prompt": "Fix grammar and improve clarity" },
    { "role": "analyst", "prompt": "Research and add current market data" },
    { "role": "designer", "prompt": "Improve slide layout and visual hierarchy" }
  ],
  "document_id": "abc-123"
}
```

Each teammate works on a different aspect. The editor fixes text, the analyst
adds data, the designer restructures. No conflicts because they own
different concerns.

### Competing hypotheses (debug)

```json
{
  "prompt": "Users report the export fails on documents over 50 pages",
  "teammates": [
    { "role": "hypothesis_memory", "prompt": "Investigate if this is a memory limit issue" },
    { "role": "hypothesis_timeout", "prompt": "Investigate if this is a timeout issue" },
    { "role": "hypothesis_format", "prompt": "Investigate if certain content causes the failure" }
  ]
}
```

Teammates investigate in parallel and message each other to challenge
findings. The lead synthesizes the most likely root cause.
