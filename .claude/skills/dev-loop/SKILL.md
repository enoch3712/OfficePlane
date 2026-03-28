---
name: dev-loop
description: The full develop-validate-test-review-improve loop. Use as the primary workflow after implementing any feature or fix.
argument-hint: [description of what was implemented]
---

Run the full agent development loop: plan -> validate -> test -> review -> improve (repeat until all pass).

> **Project config:** Read `harness.config.sh` at the project root to get `HARNESS_PROJECT_SLUG` and command prefixes.

## The Loop

```
TEST PLAN --> VALIDATE --> TEST --> REVIEW --> (all pass?) --> DOC CHECK --> DONE
                ^                                  | no           | no
                +---------- IMPROVE <--------------+<-------------+
```

**Max iterations:** 5. If not converging, stop and report what was tried.

## Step 0: TEST PLAN (runs once)

Analyze what changed and produce a **test contract** and a **doc contract**.

### 0a. Feature decomposition

Run `git diff main --name-only` to identify changed files. Group changes into independently testable features F1, F2, ..., Fn.

### 0b. Risk assessment

Score each feature:

| Axis | Low | Medium | High |
|------|-----|--------|------|
| **Blast radius** | Internal helper | Single endpoint | Cross-service, user-facing |
| **Likelihood of failure** | Simple CRUD | New logic, follows patterns | New integration, async |
| **Detection difficulty** | Loud crash (500) | Wrong response shape | Silent wrong data |

Any axis High -> CRITICAL. Two Medium -> HIGH. Otherwise MEDIUM/LOW.

### 0c. Test case design

CRITICAL/HIGH: happy path + boundary + error + auth.
MEDIUM: happy path + 1 error.
LOW: 1 smoke test.

### 0d. Write the test contract

Write to `/tmp/.test-contract-officeplane.md`:

```markdown
# Test Contract — [feature description]
Generated: [timestamp]

## Features
| # | Feature | Risk | Required Layers |
|---|---------|------|-----------------|
| F1 | ... | CRITICAL | pytest, manual |

## Required Test Cases
- [ ] F1: Happy path — [description] [pytest] CRITICAL
- [ ] F1: Error path — [description] [pytest] HIGH
```

### 0e. Write the doc contract

Write to `/tmp/.doc-contract-officeplane.md`:

```markdown
# Doc Contract — [feature description]
Generated: [timestamp]

## Required Doc Updates
- [ ] CLAUDE.md updated for new endpoint [HIGH]
- [ ] docs/ updated [MEDIUM]

## Not Applicable
- ...
```

## Step 1: VALIDATE

```bash
./scripts/check-all.sh
```

Pipeline: ruff check -> ruff format -> pytest -> tsc -> eslint -> build.

**Hard failure -> fix and re-run.**
**Advisory warnings -> note and continue.**

## Step 2: TEST

### 2a. Automated tests:
```bash
docker compose exec -T api python -m pytest tests/ -x -q
```

If frontend changed:
```bash
cd ui && npm run build
```

### 2b. E2E verification against the running system:

Use curl against `localhost:8001` for API endpoints. Check every `[manual]` item in the contract.

**If any test fails -> fix, return to Step 1.**

## Step 3: REVIEW

Run specialized agent reviews based on what changed:

- Backend `.py` files -> **arch-guardian**, **security-auditor**
- Frontend `.ts`/`.tsx` files -> **ui-guardian**
- Test files -> **test-inspector**
- **Always** run **test-inspector** with the test contract

When delegating to test-inspector, include:
> Read the test contract at `/tmp/.test-contract-officeplane.md`. For each unchecked CRITICAL/HIGH item, verify whether a test exists. If covered, change `- [ ]` to `- [x]`. Uncovered CRITICAL/HIGH = FAIL.

Run applicable reviewers in parallel.

**Any FAIL -> fix, return to Step 1.**
**Only WARN -> continue.**

## Step 4: ENTROPY CHECK (optional)

For major features only — delegate to **entropy-sweeper** with `--dry-run`.

## Step 5: DOC CHECK

Verify the doc contract at `/tmp/.doc-contract-officeplane.md`:
1. For each `- [ ]` item, check if the doc was updated
2. If not, update it now, then check it off
3. Uncovered HIGH -> FAIL, MEDIUM -> WARN

## Step 6: DONE

When all checks pass:

1. Signal review completion:
   ```bash
   touch /tmp/.claude-reviewed-officeplane
   ```
2. Report contract status
3. Report clean summary
4. List any WARN items for human attention

## Rules

- Never skip validation to save time
- Fix one category at a time (lint -> types -> tests -> review)
- If stuck in a loop, stop and explain
- After 5 iterations, escalate to user
