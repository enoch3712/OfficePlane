---
name: validate
description: Run all backend and frontend quality checks. Use after making code changes to verify nothing is broken.
disable-model-invocation: true
argument-hint: [backend|frontend|all]
---

Run `scripts/check-all.sh` for the requested scope. Default is `all` if no argument is given.

```bash
./scripts/check-all.sh $ARGUMENTS
```

## What it runs

**Backend:** ruff check → ruff format → ty check (advisory) → python -m checks (advisory) → pytest

**Frontend:** tsc → eslint → build

## Output tiers

- **Pass** (✓) — check succeeded
- **Warn** (⚠) — advisory finding (pre-existing drift, ty diagnostics) — does not block
- **Fail** (✗) — hard failure — blocks pipeline, must fix before proceeding

## Behavior

- If `$ARGUMENTS` is `backend`, run only backend checks.
- If `$ARGUMENTS` is `frontend`, run only frontend checks.
- If `$ARGUMENTS` is `all` or empty, run both.
- Exit code 0 if no hard failures (warnings are advisory only).
- On success, report a clean summary of what passed and any advisory warnings.
- On failure, stop and report clearly what failed and how to fix it.
