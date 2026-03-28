---
name: review-arch
description: Run architecture review on recent backend changes.
argument-hint: [commit-range]
---

Delegate to the **arch-guardian** agent to review recent backend changes for architecture compliance.

1. Determine the diff: `$ARGUMENTS` or `git diff HEAD~1`
2. Delegate to `arch-guardian` with the diff
3. Report findings
