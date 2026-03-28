# Core Beliefs — Patterns We Enforce

> "Capture human taste as documentation updates or encode directly into tooling." — OpenAI, Harness Engineering

This document records the team's design taste — patterns and conventions that must be followed consistently. Each belief starts here, then gets promoted into a mechanical check (`checks/`) when it's been fixed more than once.

**Escalation ladder:** Document here → Lint in `checks/` → Fix via entropy-sweeper → Prevent via CI

---

## Agent-Friendly Codebase

These beliefs make the codebase safe for agents to write all the code.

- **If it's not in the repo, it doesn't exist.** Slack threads, Google Docs, tribal knowledge — agents can't read them. Every rule, every decision, every convention lives in `docs/` or `CLAUDE.md`.
- **Error messages are agent prompts.** Lint failures and check violations include the fix instruction. Agents read stderr — make it actionable.
- **Agents copy what exists — even the bad stuff.** One bad pattern in one file becomes ten. Kill bad patterns fast, or they multiply.
- **When docs fall short, promote to code.** A rule only in docs will be violated. A rule in a linter won't.
- **Progressive disclosure.** CLAUDE.md is a map (~100 lines of pointers). Deep knowledge lives in `docs/`. Never front-load everything.
- **Hard types enforce clarity.** Strong types, strict interfaces, Protocols — types are documentation that the compiler checks. Agents can't misuse what the type system won't allow.
- **Named parameters everywhere.** `create_agent(*, name, business_id, persona_id)` — never positional. Agents (and humans) can't swap arguments when every call site reads like a sentence.
- **DDD hexagonal is the north star.** Pure domain, ports as contracts, adapters as implementations. The architecture is the agent's guardrail — it physically cannot import the wrong layer.
- **Structured logging, not prose.** `log.info("agent_published", agent_id=id, version=v)` — not `print(f"Published agent {id}")`. Agents debug by grepping structured fields, not parsing English.
- **Observability is agent-readable.** Logs + metrics + traces exposed locally. An agent that can't see what the app is doing can't fix what the app is doing.
- **Enforce invariants, not implementations.** Rigid boundaries (layers, naming, auth). Flexible interiors. Tell agents WHERE the walls are, not HOW to decorate the room.
- **The workflow is the quality.** `/validate` → `/dev-loop` → `/entropy-sweep`. The defined workflow catches drift. Skipping steps is how entropy wins.
- **Agent-to-agent review loop.** Agents review their own changes, request additional reviews, respond to feedback. Human review is optional — the arch-guardian, security-auditor, and ddd-solid-reviewer catch what linters can't. Iterate until all reviewers pass.
- **Specialized subagents preserve taste.** Each subagent owns one domain of quality: architecture, security, DDD, FSD, tests, entropy. Teams of focused agents beat one generalist — they don't forget rules, they don't get tired, they don't drift.
- **Documentation is the source of truth, not the afterthought.** If a convention isn't in `core-beliefs.md`, it can't be enforced. If an ADR isn't recorded, the decision will be relitigated. Docs drift = code drift. The entropy-sweeper catches both.
- **This is a code-for-agents-first codebase.** Every design choice optimizes for agent comprehension first, human second. Agents read this code more than humans do — make it obvious for them.
- **Maintainability is entropy prevention.** Small files, small functions, single responsibility, consistent naming — code that's easy to understand is code that agents won't corrupt. Entropy grows in complexity and hides in ambiguity.
- **E2E tests are mandatory, not optional.** Every feature gets real integration tests using the full local stack. Agents can't verify their work without tests. No tests = no confidence = compounding bugs.
- **Local dev must be trivial.** `./scripts/dev.sh` boots everything. One command. If an agent can't start the app, it can't develop the app. Docker Compose, seed data, hot reload — all working out of the box.
- **One worktree per change.** The app boots from any git worktree so agents can run isolated instances per change. No shared state, no port conflicts, no "works on my branch" problems.

---

## Backend (Python)

### Architecture

- **Hexagonal dependency direction is absolute.** Domain imports nothing. Application imports domain only. Infrastructure and API import inward, never outward. The only exception: `api/v1/dependencies/` (composition root) may import infrastructure for DI wiring.
  - Enforced by: `checks/layer_deps.py` (LAYER-001..005)

- **Every external service goes through a Port.** Application defines `Protocol` interfaces in `application/ports/`. Infrastructure provides concrete implementations. No direct infrastructure imports from API or application layers.
  - Enforced by: `checks/layer_deps.py` (LAYER-004, LAYER-005)

- **Domain models are pure Python.** No SQLAlchemy, no FastAPI, no framework imports in `domain/`. Domain entities encapsulate business rules, not data access.

### Security

- **Every mutation endpoint requires auth.** POST, PUT, PATCH, DELETE handlers must have a `Depends(get_current_user)` or `Depends(require_*)` parameter. Auth-issuing endpoints (login, register, refresh) are exempt.
  - Enforced by: `checks/security_patterns.py` (SEC-001)

- **No raw SQL.** All queries go through SQLAlchemy ORM or Core expressions. No `text()` with string literals, no `.execute("SELECT ...")`.
  - Enforced by: `checks/security_patterns.py` (SEC-002)

- **No hardcoded secrets.** Passwords, tokens, API keys come from environment variables or a secrets manager. Never string literals in source.
  - Enforced by: `checks/security_patterns.py` (SEC-003)

### Code Style

- **Named arguments required.** Functions with multiple parameters must use `*` separator. No positional args beyond the first.
  - Planned check: `checks/named_args.py`

- **Consistent naming.** Repository and service methods use: `get_*`, `create_*`, `update_*`, `delete_*`, `list_*`. Never `fetch_*`, `retrieve_*`, `remove_*`. Booleans use `is_*`, `has_*`, `can_*`, `should_*`.
  - Planned check: `checks/naming_consistency.py`

- **Files stay small.** Python files should not exceed 300 lines. Functions should not exceed 50 lines. Split when they grow.
  - Planned check: `checks/file_limits.py`

- **No dead code.** Unused imports, functions, and files get deleted. Commented-out code is not a backup strategy — that's what git is for.

### Testing

- **Real integration tests.** Call the live API, not mocks of mocks. Only mock external services via `app.dependency_overrides`.
- **AAA pattern.** Every test has visually distinct Arrange, Act, Assert blocks.
- **Descriptive names.** Test names read as specifications: `test_brand_user_cannot_list_business_agents`, not `test_access_fail`.
- **DRY fixtures.** Shared state lives in `conftest.py`. Use `pytest.mark.parametrize` for tests that differ only in input.

---

## Frontend (TypeScript)

### FSD Architecture

- **Layer imports flow downward only.** `app → pages → widgets → features → entities → shared`. Never import upward.
- **Import from public API only.** `import { Agent } from '@/entities/agent'` — never from internal paths like `@/entities/agent/model/types`.
- **Path aliases always.** Use `@/`, never relative `../` traversals.

### Colibri UI Kit

- **Use Colibri components.** Button, Badge, Card, Input, Dialog, Select, Avatar, Skeleton, Tooltip, Sheet come from `@/components/ui`.
- **Toast via sonner.** `import { toast } from 'sonner'` — not custom toast implementations.

---

## Promotion Log

When a belief gets enforced mechanically, record it here:

| Date | Belief | Promoted to | Trigger |
|------|--------|-------------|---------|
| 2026-03-09 | Hexagonal dependency direction | `checks/layer_deps.py` | TD-004, EP003 |
| 2026-03-09 | Auth on mutations | `checks/security_patterns.py` | TD-001, EP003 |
| 2026-03-09 | No raw SQL | `checks/security_patterns.py` | EP003 |
| 2026-03-09 | No hardcoded secrets | `checks/security_patterns.py` | EP003 |
