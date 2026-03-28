---
name: review-security
description: Run security review on recent code changes.
argument-hint: [commit-range]
---

Delegate to the **security-auditor** agent to review recent changes for security vulnerabilities.

1. Determine the diff: `$ARGUMENTS` or `git diff HEAD~1`
2. Delegate to `security-auditor` with the diff
3. Report findings with severity levels
