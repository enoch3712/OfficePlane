---
name: review-tests
description: Run a test quality review using the test-inspector subagent.
argument-hint: [commit-range or file path]
---

Run a test quality review of recent test changes.

## Steps

1. Determine the diff to review:
   - If `$ARGUMENTS` is a commit range (e.g., `HEAD~3..HEAD`), use that
   - If `$ARGUMENTS` is a file path, review just that file
   - If `$ARGUMENTS` is empty, use `git diff HEAD~1` for the last commit
2. Delegate to the **test-inspector** subagent with the diff as context
3. Report the subagent's findings back to the user

## Important

- Checks AAA pattern, real integration tests, descriptive names, DRY fixtures
- Both backend (pytest) and frontend (Playwright) tests
- Watches for flaky patterns (sleep, timing, ordering dependencies)
