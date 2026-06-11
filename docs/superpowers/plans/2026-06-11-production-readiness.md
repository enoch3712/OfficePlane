# OfficePlane Production Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take OfficePlane from "works on my Docker stack" to a deployable, secure, tested, single-tenant production service.

**Architecture:** FastAPI backend (layered: `api/` → `management`/`content_agent`/`ingestion` → Prisma/Postgres) + Next.js UI + Redis broker + Gotenberg/LibreOffice rendering. The agent runtime (`deepagents` + `LocalShellBackend`) executes shell commands to generate documents — this is the central security concern and the main thing standing between current state and production.

**Tech Stack:** Python 3.11, FastAPI, Prisma (Postgres + pgvector), Redis, deepagents/langgraph, LiteLLM (DeepSeek), Next.js 15, Docker Compose.

**Scope note:** This is one plan covering five sub-areas (security, auth, tests, harness, deploy). They are sequenced by risk. Phases 1–2 are merge-blocking for any public exposure; 3–5 make it maintainable and shippable. Each phase produces independently testable software.

---

## Current State (verified 2026-06-11)

What works (PR #3, branch `fix/deepseek-pro-generation-pipeline`):
- Upload → ingestion → generate-pptx/docx on `deepseek-v4-pro`, valid OOXML
- UI generate workflow streaming end-to-end at `localhost:3001`
- Prisma migrations applied to the dev DB

Known blockers (from arch + security review):
1. `LocalShellBackend` runs agent shell commands unsandboxed, in the same process env as live API keys
2. `POST /api/jobs/run` takes unvalidated query params straight into that shell pathway
3. No authentication on any endpoint (including SSE streams that echo workspace file contents)
4. CORS `allow_origins=["*"]` with `allow_credentials=True`
5. Live API keys sat in `.env` on disk (rotate)
6. Container image lacks `ruff`/`pytest` → `check-all.sh` can't run → harness is decorative
7. CLAUDE.md says UI is on `:3000`; it's actually `:3001`
8. DB was on hand-written `init.sql`, not migration history — no reproducible schema provisioning
9. `task_queue.py` is 528 lines with 11 bare `print()` calls

---

## File Structure

New files this plan creates:
- `src/officeplane/api/auth.py` — API-key auth dependency, single shared secret from env
- `src/officeplane/content_agent/sandbox.py` — sanitized subprocess env + workspace-confinement helper
- `src/officeplane/api/schemas_jobs.py` — Pydantic request bodies for `/api/jobs/run`
- `tests/api/test_auth.py` — auth dependency tests
- `tests/content_agent/test_sandbox.py` — env-scrubbing + path-confinement tests
- `tests/content_agent/test_drivers_events.py` — event normalizer regression tests
- `tests/management/test_task_queue_json.py` — Json-wrapping regression tests
- `.env.example` — placeholder-only template
- `docker/Dockerfile` — add dev tooling to a test stage
- `docs/DEPLOY.md` — deployment runbook

Files modified:
- `src/officeplane/api/main.py` — CORS lockdown, mount auth
- `src/officeplane/api/jobs_routes.py:133` — validated body, auth, driver allowlist
- `src/officeplane/api/generate_routes.py`, `jobs_routes.py` stream handlers — auth on SSE
- `src/officeplane/content_agent/drivers.py:40-48` — use sandbox helper
- `src/officeplane/management/task_queue.py` — split + replace prints with logging
- `CLAUDE.md` — fix port, document migration provisioning

---

## Phase 1 — Security Hardening (merge-blocking)

### Task 1: Sandbox the agent shell environment

**Files:**
- Create: `src/officeplane/content_agent/sandbox.py`
- Modify: `src/officeplane/content_agent/drivers.py:40-48`
- Test: `tests/content_agent/test_sandbox.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/content_agent/test_sandbox.py
import os
from pathlib import Path
import pytest
from officeplane.content_agent.sandbox import scrubbed_env, assert_within_root


def test_scrubbed_env_drops_secrets(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-secret")
    monkeypatch.setenv("GOOGLE_API_KEY", "g-secret")
    monkeypatch.setenv("DATABASE_URL", "postgres://x")
    monkeypatch.setenv("PATH", "/usr/bin")
    env = scrubbed_env()
    assert "DEEPSEEK_API_KEY" not in env
    assert "GOOGLE_API_KEY" not in env
    assert "DATABASE_URL" not in env
    assert env["PATH"] == "/usr/bin"  # non-secret keys survive


def test_assert_within_root_rejects_escape(tmp_path):
    root = tmp_path / "workspaces"
    root.mkdir()
    with pytest.raises(ValueError):
        assert_within_root(Path("/etc/passwd"), root)


def test_assert_within_root_accepts_child(tmp_path):
    root = tmp_path / "workspaces"
    (root / "job1").mkdir(parents=True)
    # returns the resolved path, does not raise
    assert assert_within_root(root / "job1", root) == (root / "job1").resolve()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api python -m pytest tests/content_agent/test_sandbox.py -v`
Expected: FAIL with "No module named officeplane.content_agent.sandbox"

- [ ] **Step 3: Write minimal implementation**

```python
# src/officeplane/content_agent/sandbox.py
"""Confinement helpers for the agent's shell execution.

The agent runs arbitrary shell via deepagents LocalShellBackend. These
helpers (1) scrub provider secrets from the child environment so a
prompt-injected `printenv` cannot exfiltrate keys, and (2) assert any
path the agent is handed stays under the workspace root.
"""

from __future__ import annotations

import os
from pathlib import Path

# Substrings that mark an env var as a secret. Conservative: drop on match.
_SECRET_MARKERS = ("API_KEY", "SECRET", "TOKEN", "PASSWORD", "DATABASE_URL")


def scrubbed_env() -> dict[str, str]:
    """Return a copy of the process env with secret-looking vars removed."""
    return {
        k: v
        for k, v in os.environ.items()
        if not any(marker in k.upper() for marker in _SECRET_MARKERS)
    }


def assert_within_root(path: Path, root: Path) -> Path:
    """Resolve ``path`` and confirm it is ``root`` or a descendant.

    Raises ValueError on escape (``..`` or absolute path outside root).
    """
    resolved = path.resolve()
    root_resolved = root.resolve()
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError(f"path {resolved} escapes workspace root {root_resolved}")
    return resolved
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api python -m pytest tests/content_agent/test_sandbox.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Wire the sandbox into the SDK driver**

In `src/officeplane/content_agent/drivers.py`, modify `DeepAgentsSDKDriver.astream` (lines ~40-48). The current code:

```python
        chat_model = build_chat_model(ModelConfig(model=model))
        backend = LocalShellBackend(root_dir=str(workspace))
```

Change to confine the workspace and scrub the env. `LocalShellBackend` in deepagents 0.5.8 accepts `virtual_mode` and an `env` mapping:

```python
        from officeplane.content_agent.sandbox import scrubbed_env

        chat_model = build_chat_model(ModelConfig(model=model))
        backend = LocalShellBackend(
            root_dir=str(workspace),
            virtual_mode=True,
            env=scrubbed_env(),
        )
```

> Note: if the installed `LocalShellBackend` signature does not accept `env`, fall back to setting the scrubbed env on the subprocess by exporting it before agent launch — but verify the signature first with `docker compose exec -T api python -c "import inspect, deepagents.backends as b; print(inspect.signature(b.LocalShellBackend.__init__))"` and adapt. Do not skip the scrub.

- [ ] **Step 6: Verify the agent still generates with scrubbed env + virtual_mode**

Run a live generate job and confirm it completes:
```bash
docker compose restart api && sleep 6
curl -s -X POST http://localhost:8001/api/jobs -H "Content-Type: application/json" \
  -d '{"skill":"generate-pptx","prompt":"x","params":{"source_document_ids":[],"brief":"sandbox smoke test, two slides"}}'
```
Expected: job enqueues; poll `/api/jobs/{id}` to `completed`. (Use a real source_document_id from `GET /api/documents` if the skill requires one.)

- [ ] **Step 7: Verify secrets are no longer reachable from the agent shell**

Drive a generate job whose brief instructs the agent to `printenv` and confirm `DEEPSEEK_API_KEY` is absent from the streamed tool output. Capture the SSE stream:
```bash
# After enqueue, read the stream and grep
curl -s -N http://localhost:8001/api/jobs/{id}/stream | grep -i "DEEPSEEK_API_KEY" || echo "SECRET NOT LEAKED (good)"
```
Expected: `SECRET NOT LEAKED (good)`

- [ ] **Step 8: Commit**

```bash
git add src/officeplane/content_agent/sandbox.py src/officeplane/content_agent/drivers.py tests/content_agent/test_sandbox.py
git commit -m "fix(content-agent): sandbox agent shell — scrub secrets, confine workspace"
```

---

### Task 2: Validate and lock down `POST /api/jobs/run`

**Files:**
- Create: `src/officeplane/api/schemas_jobs.py`
- Modify: `src/officeplane/api/jobs_routes.py:132-150`
- Test: `tests/api/test_jobs_run_validation.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_jobs_run_validation.py
import pytest
from httpx import AsyncClient, ASGITransport
from officeplane.api.main import create_app


@pytest.fixture
async def client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_run_rejects_empty_instruction(client):
    r = await client.post("/api/jobs/run", json={"instruction": ""})
    assert r.status_code == 422


async def test_run_rejects_unknown_driver(client):
    r = await client.post(
        "/api/jobs/run",
        json={"instruction": "hello", "driver": "../evil"},
    )
    assert r.status_code == 422


async def test_run_rejects_oversized_instruction(client):
    r = await client.post(
        "/api/jobs/run", json={"instruction": "x" * 5000}
    )
    assert r.status_code == 422
```

> If `create_app` is not the factory name, check `main.py` — it uses `app.add_middleware(...)`; find the app construction and expose a factory if needed. Auth (Task 4) will later require a header; this test runs before auth is mounted, so it stays valid. After Task 4, add the auth header to these requests.

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api python -m pytest tests/api/test_jobs_run_validation.py -v`
Expected: FAIL — endpoint currently accepts these (202) because params are unvalidated query strings.

- [ ] **Step 3: Write the request schema**

```python
# src/officeplane/api/schemas_jobs.py
from __future__ import annotations

from typing import Literal, Optional
from pydantic import BaseModel, Field

DriverName = Literal["deepagents_sdk", "deepagents_cli"]


class RunRequest(BaseModel):
    instruction: str = Field(..., min_length=1, max_length=4000)
    model: Optional[str] = Field(None, max_length=128)
    driver: DriverName = "deepagents_sdk"
```

- [ ] **Step 4: Rewrite the endpoint to take a body**

In `src/officeplane/api/jobs_routes.py`, replace the `run` handler signature (line ~133):

```python
from officeplane.api.schemas_jobs import RunRequest


@router.post("/run", status_code=202, response_model=JobResponse)
async def run(request: RunRequest):
    """One-off agent instruction without a specific skill."""
    task = await task_queue.enqueue_task(
        task_type="agent_run",
        payload={
            "instruction": request.instruction,
            "driver": request.driver,
            "model": request.model,
        },
        task_name=f"Run: {request.instruction[:60]}",
        priority="NORMAL",
        max_retries=1,
    )
    # ... keep the rest of the original body (stream creation, response) unchanged
```

- [ ] **Step 5: Run test to verify it passes**

Run: `docker compose exec -T api python -m pytest tests/api/test_jobs_run_validation.py -v`
Expected: PASS (3 passed)

- [ ] **Step 6: Commit**

```bash
git add src/officeplane/api/schemas_jobs.py src/officeplane/api/jobs_routes.py tests/api/test_jobs_run_validation.py
git commit -m "fix(api): validate POST /api/jobs/run body, allowlist driver"
```

---

### Task 3: Lock down CORS

**Files:**
- Modify: `src/officeplane/api/main.py:78-84`
- Test: `tests/api/test_cors.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_cors.py
import os
import pytest
from httpx import AsyncClient, ASGITransport
from officeplane.api.main import create_app


async def test_cors_reflects_only_allowed_origin(monkeypatch):
    monkeypatch.setenv("OFFICEPLANE_CORS_ORIGINS", "http://localhost:3001")
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/health", headers={"Origin": "http://evil.com"})
        assert r.headers.get("access-control-allow-origin") != "http://evil.com"
        assert r.headers.get("access-control-allow-origin") != "*"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api python -m pytest tests/api/test_cors.py -v`
Expected: FAIL — wildcard reflects any origin.

- [ ] **Step 3: Replace wildcard CORS with env-driven allowlist**

In `src/officeplane/api/main.py` (lines ~78-84):

```python
import os

_cors_origins = [
    o.strip()
    for o in os.getenv(
        "OFFICEPLANE_CORS_ORIGINS", "http://localhost:3000,http://localhost:3001"
    ).split(",")
    if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api python -m pytest tests/api/test_cors.py -v`
Expected: PASS

- [ ] **Step 5: Add the var to docker-compose and .env.example**

Add `- OFFICEPLANE_CORS_ORIGINS=${OFFICEPLANE_CORS_ORIGINS:-http://localhost:3000,http://localhost:3001}` to the `api` service env in `docker-compose.yml`, and a placeholder line in `.env.example`.

- [ ] **Step 6: Commit**

```bash
git add src/officeplane/api/main.py tests/api/test_cors.py docker-compose.yml .env.example
git commit -m "fix(api): replace wildcard CORS with env-driven origin allowlist"
```

---

### Task 4: Rotate keys and add `.env.example`

**Files:**
- Create: `.env.example`
- Modify: `CLAUDE.md` (add a secrets note)

- [ ] **Step 1: Create `.env.example` with placeholders only**

```bash
# .env.example
GOOGLE_API_KEY=your-google-api-key-here
DEEPSEEK_API_KEY=your-deepseek-api-key-here
OPENAI_API_KEY=
OFFICEPLANE_INGESTION_MODE=text
OFFICEPLANE_INGESTION_MODEL=deepseek/deepseek-v4-flash
OFFICEPLANE_AGENT_MODEL_FLASH=deepseek/deepseek-v4-flash
OFFICEPLANE_AGENT_MODEL_PRO=deepseek/deepseek-v4-pro
OFFICEPLANE_AGENT_MODEL=deepseek/deepseek-v4-pro
CONTENT_AGENT_MODEL=deepseek/deepseek-v4-pro
OFFICEPLANE_AGENT_TEMPERATURE=0.0
OFFICEPLANE_IMAGE_PROVIDER=gemini
OFFICEPLANE_CORS_ORIGINS=http://localhost:3000,http://localhost:3001
OFFICEPLANE_API_KEY=generate-a-long-random-string
```

- [ ] **Step 2: Confirm `.env` stays gitignored**

Run: `git check-ignore .env`
Expected: prints `.env`. If it does not, add `.env` to `.gitignore` and commit that first.

- [ ] **Step 3: Rotate the exposed keys (manual, out of band)**

The Google and DeepSeek keys in the working-tree `.env` were visible during development. Rotate both in their respective consoles, paste the new values into the local `.env` only. This is a human step — note it in the PR description; nothing to commit.

- [ ] **Step 4: Commit the example**

```bash
git add .env.example
git commit -m "chore: add .env.example with placeholder secrets"
```

---

## Phase 2 — Authentication (merge-blocking for public exposure)

> Single-tenant API-key auth. This is the minimum that closes the "anyone who guesses a job UUID streams your documents" hole. Multi-user auth (sessions, RBAC) is explicitly out of scope — YAGNI until there are multiple users.

### Task 5: API-key auth dependency

**Files:**
- Create: `src/officeplane/api/auth.py`
- Test: `tests/api/test_auth.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_auth.py
import pytest
from fastapi import FastAPI, Depends
from httpx import AsyncClient, ASGITransport
from officeplane.api.auth import require_api_key


def _app(monkeypatch):
    monkeypatch.setenv("OFFICEPLANE_API_KEY", "secret123")
    app = FastAPI()

    @app.get("/guarded", dependencies=[Depends(require_api_key)])
    async def guarded():
        return {"ok": True}

    return app


async def test_missing_key_rejected(monkeypatch):
    transport = ASGITransport(app=_app(monkeypatch))
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/guarded")
        assert r.status_code == 401


async def test_wrong_key_rejected(monkeypatch):
    transport = ASGITransport(app=_app(monkeypatch))
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/guarded", headers={"X-API-Key": "nope"})
        assert r.status_code == 401


async def test_correct_key_accepted(monkeypatch):
    transport = ASGITransport(app=_app(monkeypatch))
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/guarded", headers={"X-API-Key": "secret123"})
        assert r.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api python -m pytest tests/api/test_auth.py -v`
Expected: FAIL — "No module named officeplane.api.auth"

- [ ] **Step 3: Write the auth dependency**

```python
# src/officeplane/api/auth.py
"""Single shared-secret API-key auth.

Set OFFICEPLANE_API_KEY in the environment. Clients send it in the
X-API-Key header. If the env var is unset, auth is DISABLED (dev mode)
and a warning is logged once at startup — never silently open in prod.
"""

from __future__ import annotations

import logging
import os
import secrets

from fastapi import Header, HTTPException, status

log = logging.getLogger("officeplane.api.auth")


async def require_api_key(x_api_key: str | None = Header(default=None)) -> None:
    expected = os.getenv("OFFICEPLANE_API_KEY")
    if not expected:
        # Dev mode: no key configured. Allow, but make it loud.
        log.warning("OFFICEPLANE_API_KEY unset — API auth is DISABLED")
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid or missing API key",
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api python -m pytest tests/api/test_auth.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/officeplane/api/auth.py tests/api/test_auth.py
git commit -m "feat(api): add shared-secret API-key auth dependency"
```

---

### Task 6: Mount auth on mutating + stream routes

**Files:**
- Modify: `src/officeplane/api/main.py` (router include) OR each router
- Test: `tests/api/test_auth_mounted.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_auth_mounted.py
import pytest
from httpx import AsyncClient, ASGITransport
from officeplane.api.main import create_app


async def test_documents_upload_requires_key(monkeypatch):
    monkeypatch.setenv("OFFICEPLANE_API_KEY", "k")
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.post("/api/documents/upload")
        assert r.status_code == 401


async def test_health_is_public(monkeypatch):
    monkeypatch.setenv("OFFICEPLANE_API_KEY", "k")
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/health")
        assert r.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T api python -m pytest tests/api/test_auth_mounted.py -v`
Expected: FAIL — upload returns 422/202, not 401.

- [ ] **Step 3: Apply auth to routers, leave health/metrics public**

In `src/officeplane/api/main.py`, where routers are included, add the dependency to the app-level include for the `/api` routers. Keep `/health` and `/metrics` outside. Example:

```python
from fastapi import Depends
from officeplane.api.auth import require_api_key

_guard = [Depends(require_api_key)]

app.include_router(documents_router, dependencies=_guard)
app.include_router(jobs_router, dependencies=_guard)
app.include_router(generate_router, dependencies=_guard)
# ... apply _guard to every /api router. Do NOT guard health/metrics.
```

> SSE stream endpoints (`/api/jobs/{id}/stream`, `/api/generate/{id}/stream`) live in the guarded routers, so they inherit auth. Browsers can't set `X-API-Key` on `EventSource` — the UI must fetch streams via `fetch()` with the header (it already uses a client wrapper; update `NEXT_PUBLIC` config to pass the key, or proxy through the Next.js server). Note this in the UI follow-up.

- [ ] **Step 4: Run test to verify it passes**

Run: `docker compose exec -T api python -m pytest tests/api/test_auth_mounted.py -v`
Expected: PASS

- [ ] **Step 5: Verify the full suite still passes**

Run: `docker compose exec -T api python -m pytest tests/ -q`
Expected: existing tests pass (set `OFFICEPLANE_API_KEY` unset in test env so legacy tests stay in dev-mode, OR add the header in a conftest fixture).

- [ ] **Step 6: Commit**

```bash
git add src/officeplane/api/main.py tests/api/test_auth_mounted.py
git commit -m "feat(api): require API key on /api routes, keep health public"
```

---

## Phase 3 — Harness Repair + Test Coverage

### Task 7: Put dev tooling in the container so the harness runs

**Files:**
- Modify: `docker/Dockerfile`
- Test: manual verification

- [ ] **Step 1: Add dev deps to the image**

In `docker/Dockerfile`, after the content-agent deps install (line ~53-58), add:

```dockerfile
# Dev/test tooling so the quality harness runs inside the container
RUN pip install --no-cache-dir \
  "pytest>=8.0.0" "pytest-asyncio>=0.23.0" "httpx>=0.27.0" \
  "ruff>=0.6.0"
```

- [ ] **Step 2: Rebuild and verify tools resolve**

Run:
```bash
docker compose build api && docker compose up -d api && sleep 6
docker compose exec -T api ruff --version
docker compose exec -T api python -m pytest --version
```
Expected: both print versions.

- [ ] **Step 3: Verify check-all.sh runs end-to-end**

Run: `./scripts/check-all.sh backend`
Expected: ruff + pytest execute (failures OK — point is the harness runs, not that it's green yet).

- [ ] **Step 4: Commit**

```bash
git add docker/Dockerfile
git commit -m "build: install pytest+ruff in api image so harness runs"
```

---

### Task 8: Regression tests for the three bugs fixed in PR #3

**Files:**
- Create: `tests/management/test_task_queue_json.py`
- Create: `tests/content_agent/test_drivers_events.py`
- Test: themselves

- [ ] **Step 1: Write the Json-wrapping regression test**

```python
# tests/management/test_task_queue_json.py
import pytest
from officeplane.management.task_queue import task_queue


async def test_enqueue_accepts_dict_payload():
    """Regression: raw dict payloads used to crash Prisma with a
    misleading documentId error. They must enqueue cleanly now."""
    task = await task_queue.enqueue_task(
        task_type="probe",
        payload={"nested": {"a": 1}, "list": [1, 2, 3]},
        task_name="json probe",
    )
    assert task["id"]
    # payload round-trips back as a dict, not a JSON string
    fetched = await task_queue.get_task(task["id"])
    assert fetched["payload"]["nested"]["a"] == 1
```

> Verify `get_task` is the read method name in `task_queue.py`; adjust if it differs. This test needs the DB — it runs in the container against Postgres.

- [ ] **Step 2: Write the event-normalizer regression test**

```python
# tests/content_agent/test_drivers_events.py
from officeplane.content_agent.drivers import _normalize_sdk_event


def test_normalizes_v2_dict_stream_event():
    class Chunk:
        content = "hello"

    event = {"event": "on_chat_model_stream", "name": "model",
             "data": {"chunk": Chunk()}}
    out = _normalize_sdk_event(event)
    assert out.type == "delta"
    assert out.data["text"] == "hello"


def test_normalizes_list_content_chunks():
    class Chunk:
        content = [{"text": "a"}, {"text": "b"}]

    event = {"event": "on_chat_model_stream", "name": "model",
             "data": {"chunk": Chunk()}}
    out = _normalize_sdk_event(event)
    assert out.data["text"] == "ab"


def test_tool_start_event():
    event = {"event": "on_tool_start", "name": "execute",
             "data": {"input": {"cmd": "ls"}}}
    out = _normalize_sdk_event(event)
    assert out.type == "tool_call"
    assert out.data["name"] == "execute"
```

- [ ] **Step 3: Run both, verify they pass**

Run: `docker compose exec -T api python -m pytest tests/content_agent/test_drivers_events.py tests/management/test_task_queue_json.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/management/test_task_queue_json.py tests/content_agent/test_drivers_events.py
git commit -m "test: regression cover Json wrapping + v2 event normalizer"
```

---

### Task 9: End-to-end generation smoke test

**Files:**
- Create: `tests/agent/test_generation_e2e.py`

- [ ] **Step 1: Write the e2e test (marked, opt-in — hits the live model)**

```python
# tests/agent/test_generation_e2e.py
import os
import pytest
from httpx import AsyncClient, ASGITransport
from officeplane.api.main import create_app

pytestmark = pytest.mark.skipif(
    not os.getenv("OFFICEPLANE_E2E"),
    reason="set OFFICEPLANE_E2E=1 to run live-model e2e",
)


async def test_generate_pptx_completes_on_pro():
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://test", timeout=180) as c:
        # upload a tiny doc
        with open("E2E Test Document.docx", "rb") as f:
            up = await c.post("/api/documents/upload", files={"file": f})
        doc_id = up.json()["id"]
        # generate
        r = await c.post("/api/jobs", json={
            "skill": "generate-pptx", "prompt": "two-slide summary",
            "params": {"source_document_ids": [doc_id], "brief": "summary", "slide_count": 2},
        })
        job_id = r.json()["job_id"]
        # poll
        import asyncio
        for _ in range(18):
            await asyncio.sleep(10)
            s = (await c.get(f"/api/jobs/{job_id}")).json()
            if s["status"] in ("completed", "failed"):
                break
        assert s["status"] == "completed"
        assert "deepseek-v4-pro" in s["result"]["output"]["model"]
```

- [ ] **Step 2: Run it opt-in**

Run: `docker compose exec -T -e OFFICEPLANE_E2E=1 api python -m pytest tests/agent/test_generation_e2e.py -v`
Expected: PASS (≈60s). Without the env var it SKIPs — keeps CI fast and offline.

- [ ] **Step 3: Commit**

```bash
git add tests/agent/test_generation_e2e.py
git commit -m "test: opt-in e2e for generate-pptx on deepseek-v4-pro"
```

---

### Task 10: Split `task_queue.py` and kill bare prints

**Files:**
- Modify: `src/officeplane/management/task_queue.py`
- Create: `src/officeplane/management/task_handlers.py`

- [ ] **Step 1: Add a module logger, replace prints**

At the top of `task_queue.py` add `log = logging.getLogger("officeplane.management.task_queue")` (import logging). Replace each of the 11 `print(...)` calls with the matching `log.info/warning/error(...)`. Keep the message text.

- [ ] **Step 2: Run the existing task-queue test**

Run: `docker compose exec -T api python -m pytest tests/test_task_queue_skill_dispatch.py -v`
Expected: PASS (behavior unchanged).

- [ ] **Step 3: Extract handler methods to get under 300 lines**

Move `_run_skill_job` (and its legacy branch) and `_run_content_generate` into `task_handlers.py` as functions taking the db/task, and call them from `_execute_task`. Target: `task_queue.py` under 300 lines, no function over 50.

- [ ] **Step 4: Run the test again**

Run: `docker compose exec -T api python -m pytest tests/test_task_queue_skill_dispatch.py -v`
Expected: PASS.

- [ ] **Step 5: Run mechanical checks**

Run: `docker compose exec -T api python -m checks`
Expected: `file_limits` and `naming_consistency` for `task_queue.py` now pass.

- [ ] **Step 6: Commit**

```bash
git add src/officeplane/management/task_queue.py src/officeplane/management/task_handlers.py
git commit -m "refactor(management): split task_queue, replace prints with logging"
```

---

## Phase 4 — Reproducible DB Provisioning

### Task 11: Make schema provisioning migration-based

**Files:**
- Modify: `docker/init.sql` (deprecate), `docker-compose.yml`, `docs/DEPLOY.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1: Confirm the drift root cause**

The dev DB was created from `docker/init.sql` (hand-written), so `prisma migrate` saw a non-empty, unversioned schema and required baselining. Production must provision from migrations only.

- [ ] **Step 2: Add a migration-deploy step to startup**

Add a one-shot step (compose service or entrypoint) that runs `prisma migrate deploy` against the DB before the API serves. Minimal approach — extend the api entrypoint:

```bash
# in the api container start command, before uvicorn:
python -m prisma migrate deploy --schema /app/prisma/schema.prisma || true
```

> `migrate deploy` is idempotent and only applies pending migrations. On a fresh DB it builds the whole schema; on an up-to-date DB it's a no-op.

- [ ] **Step 3: Reduce `init.sql` to extensions only**

Strip `docker/init.sql` to just `CREATE EXTENSION IF NOT EXISTS vector;` and the `plpgsql` line — let migrations own all tables. This prevents the drift that required manual baselining.

- [ ] **Step 4: Verify fresh-DB provisioning**

```bash
docker compose down -v   # wipe the volume
docker compose up -d && sleep 20
docker exec officeplane-db psql -U officeplane -d officeplane -c "\dt" | grep -c documents
```
Expected: prints `1` — schema built from migrations on a clean volume, no manual SQL.

- [ ] **Step 5: Update docs**

In `CLAUDE.md`: fix UI port (`3000` → `3001`), add a "Database provisioning" note that schema comes from `prisma migrate deploy`, not `init.sql`.

- [ ] **Step 6: Commit**

```bash
git add docker/init.sql docker-compose.yml CLAUDE.md docs/DEPLOY.md
git commit -m "build(db): provision schema via prisma migrate deploy, fix docs"
```

---

## Phase 5 — Deployment Hardening

### Task 12: Production compose + healthchecks + resource limits

**Files:**
- Modify: `docker-compose.yml` (or add `docker-compose.prod.yml`)
- Create: `docs/DEPLOY.md`

- [ ] **Step 1: Add healthchecks to api and ui**

```yaml
  api:
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')"]
      interval: 30s
      timeout: 5s
      retries: 3
      start_period: 20s
```

- [ ] **Step 2: Pin a non-root user + read-only root FS for api where possible**

The Dockerfile already creates `appuser` (uid 10001) and the source mount is `ro`. For prod, drop the source bind-mount entirely (code is baked into the image) and remove `--reload`. Add to the prod override:

```yaml
  api:
    command: uvicorn officeplane.api.main:app --host 0.0.0.0 --port 8001
    # no source volume in prod — image is the artifact
```

- [ ] **Step 3: Set resource limits**

```yaml
    deploy:
      resources:
        limits:
          memory: 2g
```

- [ ] **Step 4: Write the deploy runbook**

`docs/DEPLOY.md` covers: required env vars (with `OFFICEPLANE_API_KEY`, `OFFICEPLANE_CORS_ORIGINS`), `docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d`, migration step, smoke test (upload + generate), and key-rotation procedure.

- [ ] **Step 5: Verify prod compose boots and is healthy**

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d && sleep 25
docker compose ps   # all healthy
curl -s -H "X-API-Key: $OFFICEPLANE_API_KEY" http://localhost:8001/api/documents | head -c 80
```
Expected: services healthy, authed request returns JSON.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.prod.yml docs/DEPLOY.md
git commit -m "build: production compose override + deploy runbook"
```

---

## Self-Review Notes

- **Coverage:** security (Tasks 1-4), auth (5-6), tests (8-9), harness repair (7,10), deploy (11-12). All five requested areas have tasks.
- **Sequencing:** Phase 1+2 are merge-blocking and independent of 3-5. Phase 3 Task 7 (tooling-in-container) should ideally run first so the test steps in earlier tasks can execute — if executing strictly in order, do Task 7 before running the pytest steps in Tasks 1-6, or run those tests via a local venv with `pip install -e ".[dev]"`.
- **Out of scope (YAGNI):** multi-user auth/RBAC, rate limiting, observability/tracing backend, CI pipeline config, frontend test suite (separate plan — UI currently has zero test infra). Flag the frontend test gap as a follow-up plan.
- **Pre-existing items deferred:** CLI driver `_write_setup_script` escaping (WARN), Redis processing-set TTL (WARN) — lower risk than Phase 1, fold into a Phase 6 if desired.
