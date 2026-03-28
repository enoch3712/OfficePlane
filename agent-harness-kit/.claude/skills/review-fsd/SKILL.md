---
name: review-fsd
description: Run a Feature-Sliced Design review on frontend changes using the fsd-guardian subagent.
argument-hint: [commit-range or file path]
---

Run a Feature-Sliced Design architecture review of recent frontend changes.

## Steps

1. Determine the diff to review:
   - If `$ARGUMENTS` is a commit range (e.g., `HEAD~3..HEAD`), use that
   - If `$ARGUMENTS` is a file path, review just that file
   - If `$ARGUMENTS` is empty, use `git diff HEAD~1` for the last commit
2. Delegate to the **fsd-guardian** subagent with the diff as context
3. Report the subagent's findings back to the user

## Important

- Frontend TypeScript/React code only
- Checks FSD layer imports, barrel exports, Colibri UI Kit usage, TypeScript patterns
- For backend reviews, use `/review-arch`
