---
name: review-tests
description: Run test quality and coverage review.
argument-hint: [commit-range]
---

Delegate to the **test-inspector** agent to review test quality and coverage.

1. Determine the diff: `$ARGUMENTS` or `git diff HEAD~1`
2. If a test contract exists at `/tmp/.test-contract-officeplane.md`, include it
3. Delegate to `test-inspector` with the diff and contract
4. Report quality findings, coverage status, and completeness verdict
