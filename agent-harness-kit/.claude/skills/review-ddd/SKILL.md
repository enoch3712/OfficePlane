---
name: review-ddd
description: Run a DDD and SOLID compliance review using the ddd-solid-reviewer subagent.
argument-hint: [commit-range or file path]
---

Run a DDD & SOLID compliance review of recent code changes.

## Steps

1. Determine the diff to review:
   - If `$ARGUMENTS` is a commit range (e.g., `HEAD~3..HEAD`), use that
   - If `$ARGUMENTS` is a file path, review just that file
   - If `$ARGUMENTS` is empty, use `git diff HEAD~1` for the last commit
2. Delegate to the **ddd-solid-reviewer** subagent with the diff as context
3. Report the subagent's findings back to the user

## Important

- Checks SOLID principles, domain modeling quality, DRY, named arguments
- Particularly watches for anemic domain models and god-services
- Backend Python code only
