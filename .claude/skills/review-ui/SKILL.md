---
name: review-ui
description: Run frontend/UI review on recent changes.
argument-hint: [commit-range]
---

Delegate to the **ui-guardian** agent to review recent frontend changes for Next.js patterns and design system compliance.

1. Determine the diff: `$ARGUMENTS` or `git diff HEAD~1`
2. Delegate to `ui-guardian` with the diff
3. Report findings on App Router patterns, design system, TypeScript quality
