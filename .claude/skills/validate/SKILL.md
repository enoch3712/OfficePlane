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

**Backend:** ruff check -> ruff format -> pytest

**Frontend:** tsc -> eslint -> build

## Output tiers

- **Pass** — check succeeded
- **Warn** — advisory finding, does not block
- **Fail** — hard failure, must fix before proceeding

## Behavior

- If `$ARGUMENTS` is `backend`, run only backend checks.
- If `$ARGUMENTS` is `frontend`, run only frontend checks.
- If `$ARGUMENTS` is `all` or empty, run both.
- On success, report a clean summary.
- On failure, stop and report what failed and how to fix it.
