# Implementation Status — File Operation Flow

## Implemented

### Queue with Redis dispatch (Step 2)
- Redis 7 (alpine) added to docker-compose
- `redis_client.py` — connection pool, document locks, task dispatch, SSE pub/sub
- `task_queue.py` — rewritten to use Redis BRPOP (instant wakeup) + SETNX (doc lock)
- Graceful degradation: falls back to Postgres polling if Redis is down
- SSE streaming via Redis pub/sub (decouples worker from HTTP handler)

### Task queue atomicity (Step 2)
- `acquire_document_lock()` — Redis SETNX with TTL, Lua-script atomic release
- Workers skip tasks whose document is already locked, re-queue them
- Lock auto-expires after 10 min (prevents deadlock from crashed workers)

### Content generation agent (Step 3, new files only)
- `content_agent/` module — DeepAgents runner with OpenAI fallback
- SSE streaming of agent events
- Results saved to document store

---

## Remaining Gaps

### Gap 1: Instance = file session (Step 1)
**Current:** Instances are LibreOffice process wrappers.
**Needed:** Instance creation should copy `source_file` bytes into a workspace
and enforce one-active-instance-per-document.

### Gap 2: Agent harness for editing existing files (Step 3)
**Current:** ContentAgentRunner generates new documents from scratch.
**Needed:** A mode that loads an existing file into the workspace, lets the
agent modify it, then saves it back.

### Gap 3: pretty() function (Step 4)
**Current:** Does not exist.
**Needed:** `content_agent/pretty.py` with format-specific normalization
(DOCX style cleanup, PPTX layout normalization).
