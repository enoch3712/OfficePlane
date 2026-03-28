---
name: review-security
description: Run a security audit on recent changes using the security-auditor subagent.
argument-hint: [commit-range or file path]
---

Run a security audit of recent code changes.

## Steps

1. Determine the diff to review:
   - If `$ARGUMENTS` is a commit range (e.g., `HEAD~3..HEAD`), use that
   - If `$ARGUMENTS` is a file path, review just that file
   - If `$ARGUMENTS` is empty, use `git diff HEAD~1` for the last commit
2. Delegate to the **security-auditor** subagent with the diff as context
3. Report the subagent's findings back to the user

## Important

- Focuses on OWASP Top 10, auth patterns, input validation, secrets in code
- Pay special attention to auth-before-mutation ordering (known vulnerability pattern in this codebase)
- WARN findings need human judgment — escalate them clearly
