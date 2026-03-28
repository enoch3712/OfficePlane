---
name: entropy-sweep
description: Run an entropy sweep to detect and fix code drift — duplication, naming inconsistencies, dead code, pattern divergence, file bloat, and doc content staleness. Use weekly or after major features.
argument-hint: [backend|frontend|all] [--dry-run]
---

Run the entropy management loop: detect → classify → fix → verify.

## Default: Agent Team (parallel sweepers)

**Always use an agent team** for entropy sweeps. This maximizes coverage and speed by running multiple sweepers in parallel, each owning a subset of entropy dimensions.

### Team composition

| Scope | Sweepers | Dimensions |
|-------|----------|------------|
| `backend` | 2 | A: duplication, naming, dead code. B: pattern divergence, bloat, stale docs |
| `frontend` | 2 | A: FSD violations, dead exports, duplication. B: naming drift, test entropy, doc staleness |
| `all` | 4 | All of the above |

### How to spawn the team

1. `TeamCreate` with name `entropy-sweep-team`
2. Create 1 task per sweeper via `TaskCreate`
3. Spawn each sweeper as an `entropy-sweeper` subagent with `team_name: entropy-sweep-team`
4. Each sweeper:
   - Scans its assigned dimensions
   - Classifies findings as CRITICAL / HIGH / MEDIUM / LOW
   - Fixes CRITICAL and HIGH items (unless `--dry-run`)
   - Runs quality checks after fixes
   - Reports findings and marks its task completed
5. Team lead aggregates all findings into a single report

### Sweeper prompts (copy-paste ready)

**Backend Sweeper A** — scope: `agent_builder_backend/src/`, `agent_builder_backend/tests/`
> Scan for ENTROPY-DUP (near-identical blocks), ENTROPY-NAME (fetch_ vs get_, inconsistent prefixes), ENTROPY-DEAD (unused functions/imports/classes). Run `docker compose exec -T backend uv run python -m checks --json` for baseline. After fixes: `docker compose exec -T backend uv run ruff check --fix . && docker compose exec -T backend uv run ruff format .`

**Backend Sweeper B** — scope: `agent_builder_backend/src/`, `docs/`, `CLAUDE.md`
> Scan for ENTROPY-PATTERN (missing error handling, inconsistent response shapes), ENTROPY-BLOAT (files >300 lines, functions >50 lines), ENTROPY-DOC (stale docstrings), ENTROPY-STALE (.md files referencing paths/functions that no longer exist). After fixes: same ruff commands.

**Frontend Sweeper A** — scope: `agent_builder_frontend/src/`
> Run `./scripts/check-fsd.sh` for baseline. Scan for ENTROPY-PATTERN (FSD layer violations, upward imports), ENTROPY-DEAD (unused exports/components/hooks), ENTROPY-DUP (duplicated UI patterns). After fixes: `cd agent_builder_frontend && npx tsc --noEmit && npm run lint`

**Frontend Sweeper B** — scope: `agent_builder_frontend/src/`, `agent_builder_frontend/e2e/`, `docs/frontend/`
> Scan for ENTROPY-NAME (inconsistent file/component naming), ENTROPY-TEST (copy-pasted tests, missing parametrize), ENTROPY-STALE (docs referencing frontend paths that don't exist). After fixes: `cd agent_builder_frontend && npx tsc --noEmit`

## Steps (for each sweeper)

1. Parse scope and mode from task assignment
2. Run mechanical checks for baseline (`checks --json`, `check-fsd.sh`)
3. Scan assigned entropy categories
4. Classify each finding as CRITICAL / HIGH / MEDIUM / LOW
5. Fix CRITICAL and HIGH items (unless `--dry-run`)
6. Run quality checks to verify fixes
7. Report findings in structured table format

## Aggregation (team lead)

After all sweepers complete:
1. Collect all findings into a single report grouped by category
2. Count: total findings, CRITICAL, HIGH, MEDIUM, LOW
3. List all fixes applied
4. Note any "promotion candidates" (patterns fixed twice → should become mechanical checks)
5. **If fixes were applied and all quality checks passed**, regenerate the scorecard:
   ```bash
   ./scripts/generate-scorecard.sh --fast
   ```
   Skip if `--dry-run` or if any checks failed after fixes.

## When to use

- **Weekly:** Run `/entropy-sweep all` as a regular hygiene pass
- **Post-feature:** Run `/entropy-sweep backend` after shipping a backend feature
- **Pre-release:** Run `/entropy-sweep all --dry-run` to audit entropy before a release
- **On-demand:** When you suspect drift has accumulated

## What it catches

| Category | ID | Example |
|----------|----|---------|
| Duplication | ENTROPY-DUP | Two services with near-identical error handling blocks |
| Naming drift | ENTROPY-NAME | `fetch_agent` in one service, `get_agent` in another |
| Dead code | ENTROPY-DEAD | A service method that nothing calls |
| Pattern divergence | ENTROPY-PATTERN | An endpoint missing the standard error handling |
| File bloat | ENTROPY-BLOAT | A 400-line endpoint file that should be split |
| Stale docs | ENTROPY-DOC | A docstring referencing a removed parameter |
| Test entropy | ENTROPY-TEST | Copy-pasted test bodies that should be parametrized |
| Doc content staleness | ENTROPY-STALE | A `.md` file referencing a file path, skill, or agent that no longer exists |

## The escalation rule

If the sweeper fixes the same pattern for the **second time**, it flags it as a "promotion candidate" — a pattern that should become a mechanical check in `checks/` so it never happens again. This is the core of the anti-entropy loop:

```
Fix once  → sweeper handles it
Fix twice → promote to a mechanical check
```

## Important

- The sweeper **will modify files** (unless `--dry-run`) — review its changes before committing
- It runs full quality checks after every fix batch — safe by construction
- It never renames public API endpoints, only internal code
- It never deletes code without verifying zero references first
- For frontend-only entropy (FSD layer violations, unused exports), use scope `frontend`
- **Always spawn as a team** — single-sweeper mode is only for trivial scopes (1-2 files)
