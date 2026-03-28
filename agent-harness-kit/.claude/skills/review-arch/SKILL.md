---
name: review-arch
description: Run an architecture review on recent changes using the arch-guardian subagent.
argument-hint: [commit-range or file path]
---

Run an architecture review of recent code changes.

## Steps

1. Determine the diff to review:
   - If `$ARGUMENTS` is a commit range (e.g., `HEAD~3..HEAD`), use that
   - If `$ARGUMENTS` is a file path, review just that file
   - If `$ARGUMENTS` is empty, use `git diff HEAD~1` for the last commit
2. Delegate to the **arch-guardian** subagent with the diff as context
3. Report the subagent's findings back to the user

## Important

- This reviews **backend** code only (Python, hexagonal architecture)
- For frontend reviews, use `/review-fsd`
- The arch-guardian checks: layer dependencies, port/adapter patterns, domain purity, thin endpoints
