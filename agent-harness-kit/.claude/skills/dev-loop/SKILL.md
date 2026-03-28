---
name: dev-loop
description: The full develop-validate-test-review-improve loop. Use as the primary workflow after implementing any feature or fix.
argument-hint: [description of what was implemented]
---

Run the full agent development loop: plan → validate → test → review → improve (repeat until all pass).

> **Project config:** Before starting, read `harness.config.sh` at the project root to get `HARNESS_PROJECT_SLUG`, `BACKEND_RUN`, and `FRONTEND_DIR`. All contract paths and marker commands below use these values.

## The Loop

```
TEST PLAN ──→ VALIDATE ──→ TEST ──→ REVIEW ──→ (all pass?) ──→ ENTROPY CHECK ──→ DOC CHECK ──→ (docs pass?) ──→ SCORECARD ──→ DONE
                 ↑                                  │ no                                        │ no
                 └──────── IMPROVE ←───────────────┘←──────────────────────────────────────────┘
```

**Max iterations:** 5. If not converging, stop and report what was tried.

## Step 0: TEST PLAN (risk-based, runs once)

Before any validation, analyze what changed and produce a **test contract** and a **doc contract** — machine-readable lists of what MUST be tested and what docs MUST be updated before the loop can exit. The test-inspector in Step 3 verifies the test contract; Step 5 verifies the doc contract. Uncovered CRITICAL/HIGH items in either contract cause a FAIL.

### 0a. Feature decomposition

Run `git diff main --name-only` (or `git diff HEAD~1` if on main) to identify changed files. Group changes into independently testable features/behaviors. Name them F1, F2, ..., Fn.

For each feature, identify:
- **What it does** (1 sentence)
- **Entry points** (endpoint, UI component, CLI command, script)
- **Dependencies** (DB, external service, registry, file system)

### 0b. Risk assessment

Score each feature on three axes (Low/Medium/High):

| Axis | Low | Medium | High |
|------|-----|--------|------|
| **Blast radius** | Internal helper | Single endpoint | Cross-service, user-facing |
| **Likelihood of failure** | Simple CRUD, no new logic | New logic, but follows patterns | New integration, multiple systems, async |
| **Detection difficulty** | Loud crash (500, TypeError) | Wrong response shape | Silent wrong data, subtle state corruption |

Derive overall risk: any axis High → CRITICAL. Two Medium → HIGH. Otherwise MEDIUM/LOW.

### 0c. Test case design

For CRITICAL and HIGH risk features, list required test cases using equivalence partitioning:

1. **Happy path** — normal input, expected output
2. **Boundary cases** — empty, max, exact limits
3. **Error paths** — invalid input, missing deps, timeout, 4xx/5xx
4. **Auth/access** — wrong role, no token
5. **State transitions** — for async: all status progressions

For MEDIUM risk: happy path + 1 error path minimum.
For LOW risk: 1 smoke test sufficient.

For each test case, specify which layer:
- `[pytest]` — backend integration test
- `[postman]` — Newman regression test (if endpoint added/changed)
- `[playwright]` — browser E2E test (if UI added/changed)
- `[manual]` — curl / Playwright MCP verification against running app

### 0d. Write the test contract

Read `HARNESS_PROJECT_SLUG` from `harness.config.sh`. Write the contract to `/tmp/.test-contract-<HARNESS_PROJECT_SLUG>.md`:

```markdown
# Test Contract — [feature description]
Generated: [timestamp]

## Features
| # | Feature | Risk | Required Layers |
|---|---------|------|-----------------|
| F1 | ... | CRITICAL | pytest, postman, manual |
| F2 | ... | HIGH | pytest, manual |
| F3 | ... | LOW | pytest (smoke) |

## Required Test Cases
- [ ] F1: Happy path — [description] [pytest]
- [ ] F1: Auth guard — [description] [pytest]
- [ ] F1: Error — [description] [pytest]
- [ ] F1: Regression — [description] [postman]
- [ ] F2: Happy path — [description] [pytest]
...

## Coverage Gaps (pre-existing)
List any existing features that are ALREADY untested (from prior work).
Mark as `[gap]` — these are informational, not blocking.
```

### 0e. Write the doc contract

Analyze the same `git diff` from Step 0a. For each changed file, determine what documentation needs updating. Write the contract to `/tmp/.doc-contract-<HARNESS_PROJECT_SLUG>.md`:

**Rules for what triggers a doc update:**

| Change detected | Doc action required | Priority |
|----------------|---------------------|----------|
| New/changed endpoint | Postman collection needs updating | HIGH |
| New/changed endpoint | `docs/dev/testing.md` may need new test instructions | MEDIUM |
| Cross-service decision made | ADR should be created in `docs/adr/` | HIGH |
| Execution plan phase completed | EP checkboxes need updating | HIGH |
| Tech debt item fixed | `docs/exec-plans/tech-debt-tracker.md` needs updating | MEDIUM |
| New script/file added | Reference in CLAUDE.md if agent-facing | HIGH |
| Hooks/skills/agents changed | `docs/design/enforcement-architecture.md` needs updating | HIGH |
| New pattern/convention | `docs/design/core-beliefs.md` if it should be enforced | MEDIUM |

**Contract format:**

```markdown
# Doc Contract — [feature description]
Generated: [timestamp]

## Required Doc Updates
- [ ] Postman collection updated for POST /evals/runs [HIGH]
- [ ] ADR created for agent UUID resolution pattern [HIGH]
- [ ] EP006 checkboxes updated [HIGH]
- [ ] enforcement-architecture.md updated for new hook markers [HIGH]
- [ ] CLAUDE.md references check-fsd.sh [MEDIUM]

## Not Applicable
- No tech debt items fixed
- No new conventions introduced
```

If no doc updates are required, write the contract with an empty "Required Doc Updates" section and list all categories as "Not Applicable". The contract must always exist after Step 0 so the stop-gate can verify it.

**This step runs ONCE at the start (together with the test contract).** It does not repeat on loop iterations. If the loop cycles back from Step 5, the contract remains — the agent updates the docs and re-verifies.

## Step 1: VALIDATE (mechanical checks)

Run all quality checks via the unified entrypoint. Stop and fix on first failure before proceeding.

```bash
./scripts/check-all.sh              # all checks (backend + frontend)
./scripts/check-all.sh backend      # backend only (if only .py changed)
./scripts/check-all.sh frontend     # frontend only (if only .ts/.tsx changed)
```

Pipeline: ruff check → ruff format → ty check (advisory) → python -m checks (advisory) → pytest → tsc → eslint → build.

**If any hard failure (✗) → fix the issues and re-run validation.**
**Advisory warnings (⚠) → note them but continue to Step 2.**

## Step 2: TEST

### 2a. Automated test suites:
```bash
# Read BACKEND_RUN from harness.config.sh
$BACKEND_RUN pytest -x -q
```

If API changed, also run Newman:
```bash
docker run --rm --network host -v "$(pwd)/postman:/etc/newman" \
  postman/newman:latest run collections/agent-builder-collection.json \
  --environment environments/localhost-environment.json
```

If frontend changed:
```bash
cd $FRONTEND_DIR && npm run build
```

### 2b. E2E verification against the running system:

**This is mandatory for every change — not just infrastructure.** Pytest runs in a test container, not against the real running app. You must verify your changes work end-to-end against the live local stack.

Use the test contract from Step 0 — every `[manual]` item must be executed here. For each:
1. **What command exercises it?** (curl, `playwright-cli`, Docker command)
2. **What proves it works?** (response body, status code, log line, UI state)
3. **What is the negative case?** (what should NOT happen, what should fail gracefully)

**Tools for E2E verification:**
- **API endpoints:** `curl` against `localhost:8000` (backend), `localhost:8001` (registry)
- **UI flows:** `playwright-cli` — see `/playwright` skill for commands. Use `snapshot` to inspect page, `screenshot` to capture proof.
- **Video demos:** `playwright-cli video-start` / `video-stop` to record a flow

Run every scenario against the running services. Check off `[manual]` items in the contract as you verify them.

**Do not trust syntax checks or pytest alone.** Three bugs in a shell script passed `bash -n` and full pytest but failed when actually executed against the running system.

**If any test fails → fix the issues, return to Step 1.**

## Step 3: REVIEW

Run specialized agent reviews based on what changed:

- Backend `.py` files → delegate to **arch-guardian**, **security-auditor**, **ddd-solid-reviewer**
- Frontend `.ts`/`.tsx` files → delegate to **fsd-guardian**
- Test files → delegate to **test-inspector**
- **Always** delegate to **test-inspector** with the test contract (even if no test files changed — it checks for *missing* tests)

When delegating to test-inspector, include in the prompt:
> Read the test contract at `/tmp/.test-contract-<HARNESS_PROJECT_SLUG>.md`. For each CRITICAL/HIGH item marked `- [ ]` (unchecked), verify whether a corresponding test exists. If covered, update the line in the contract from `- [ ]` to `- [x]`. Report uncovered CRITICAL items as FAIL and uncovered HIGH items as FAIL. MEDIUM/LOW uncovered items are WARN.

**Why the edit matters:** The stop-gate hook (`quality-gate.sh`) mechanically verifies the contract — it greps for unchecked CRITICAL/HIGH lines. If any remain, the agent **cannot exit the session**. test-inspector checking off items is what unlocks the gate.

Run applicable reviewers in parallel. Collect all findings.

**If any reviewer reports FAIL → fix the issues, return to Step 1.**
**If only WARN findings → report them but continue (human can decide).**

## Step 4: ENTROPY CHECK (optional)

If this was a major feature (multiple files, new patterns introduced), run a targeted entropy sweep:

- Delegate to **entropy-sweeper** with `--dry-run` and the scope of changed files
- This is detect-only — no auto-fixes during the dev loop
- Report any CRITICAL/HIGH findings as additional WARN items

Skip this step for small changes (single-file bug fixes, config tweaks).

## Step 5: DOC CHECK (contract verification)

Verify the doc contract written in Step 0e. This is the same mechanical pattern as test-inspector verifying the test contract.

1. Read the doc contract at `/tmp/.doc-contract-<HARNESS_PROJECT_SLUG>.md`
2. For each `- [ ]` item in "Required Doc Updates":
   - Check whether the referenced doc was actually updated (file exists and was modified in the working tree or in the current diff)
   - If verified, update the line in the contract from `- [ ]` to `- [x]`
   - If NOT verified, perform the doc update now, then check it off
3. After all items are addressed, report status:
   - All items checked → PASS
   - Uncovered HIGH items remain → FAIL (update the docs and re-verify)
   - Uncovered MEDIUM items remain → WARN (note for human attention)

**Why this matters:** The stop-gate hook (`quality-gate.sh`) mechanically verifies the doc contract — it greps for unchecked HIGH lines. If any remain, the agent **cannot exit the session**. Checking off items here is what unlocks the gate.

Run `./scripts/check-docs.sh` after any doc edits to verify links and index completeness.

**If any HIGH items uncovered → update the docs, check them off, return to Step 1.**
**If only MEDIUM items uncovered → report them as WARN but continue to Step 6.**

## Step 6: SCORECARD

**Only if all checks passed and all tests passed**, regenerate the quality scorecard to capture the current state:

```bash
./scripts/generate-scorecard.sh --fast
```

This updates `docs/generated/quality-scorecard.md` and appends to `score-history.csv`. Uses `--fast` (mechanical only) during the loop — full Opus analysis is for on-demand runs.

**Skip this step if tests failed or were skipped.**

## Step 7: DONE

When all checks pass, all tests pass, and all reviewers report PASS/WARN:

1. Signal review completion to the quality gate:
   ```bash
   # Read HARNESS_PROJECT_SLUG from harness.config.sh first
   touch /tmp/.claude-reviewed-<HARNESS_PROJECT_SLUG>
   ```
2. Report test contract status:
   - How many CRITICAL/HIGH/MEDIUM items in the contract
   - How many were satisfied (checked off by test-inspector)
   - Any `[gap]` items noted for future work
3. Report doc contract status:
   - How many HIGH/MEDIUM items in the contract
   - How many were satisfied (checked off in Step 5)
   - Any MEDIUM items deferred as WARN
4. Report a clean summary of what was validated
5. List any WARN items for human attention (including entropy findings)
6. Report the iteration count

## Rules

- Never skip validation to save time
- Fix one category of issues at a time (lint first, then types, then tests, then review)
- If stuck in a loop (same error recurring), stop and explain the issue
- After 5 iterations, escalate to the user with a summary of attempts
