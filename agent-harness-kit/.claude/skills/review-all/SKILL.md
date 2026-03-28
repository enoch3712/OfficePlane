---
name: review-all
description: Run all 5 specialized reviewers on recent changes and aggregate results.
argument-hint: [commit-range]
---

Run all specialized reviewers on recent code changes and produce an aggregated report.

## Steps

1. Determine the diff to review:
   - If `$ARGUMENTS` is a commit range, use that
   - If empty, use `git diff HEAD~1`
2. Identify which files changed: backend Python, frontend TypeScript, tests, or mixed
3. Run the **relevant** reviewers in parallel based on changed files:
   - Backend `.py` files changed → **arch-guardian**, **security-auditor**, **ddd-solid-reviewer**
   - Frontend `.ts`/`.tsx` files changed → **fsd-guardian**
   - Test files changed → **test-inspector**
   - Mixed → all applicable reviewers
4. Aggregate all findings into a single report
5. Signal review completion to the quality gate:
   ```bash
   touch /tmp/.claude-reviewed-poc-agent-builder
   ```

## Output format

```
## Review Summary

### Architecture Guardian: PASS/FAIL
[findings]

### Security Auditor: PASS/WARN/FAIL
[findings]

### DDD & SOLID: PASS/FAIL
[findings]

### FSD Guardian: PASS/FAIL
[findings]

### Test Inspector: PASS/FAIL
[findings]

## Overall Verdict: PASS / NEEDS WORK / FAIL
[summary of critical items to address]
```

## Important

- Only run reviewers relevant to the changed files — don't waste time reviewing unchanged code
- Run relevant reviewers in parallel for speed
- FAIL verdict if any reviewer reports FAIL
- NEEDS WORK if only WARN findings exist
