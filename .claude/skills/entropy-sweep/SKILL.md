---
name: entropy-sweep
description: Detect and fix code drift — duplication, naming inconsistencies, dead code, file bloat. Run weekly or after major features.
argument-hint: [--dry-run] [scope: backend|frontend|all]
---

Delegate to the **entropy-sweeper** agent.

## Behavior

- If `$ARGUMENTS` contains `--dry-run`, detect only — no auto-fixes
- If `$ARGUMENTS` contains `backend`, scope to `src/officeplane/`
- If `$ARGUMENTS` contains `frontend`, scope to `ui/`
- Default: scan everything

## What it detects

1. **ENTROPY-DUP** — Near-duplicate code blocks
2. **ENTROPY-NAME** — Naming inconsistencies
3. **ENTROPY-DEAD** — Dead code, unused imports
4. **ENTROPY-PATTERN** — Pattern divergence
5. **ENTROPY-BLOAT** — File size violations (>300 lines)
6. **ENTROPY-DOC** — Stale documentation references

## Output

Entropy Sweep Report with findings categorized by severity (CRITICAL/HIGH/MEDIUM/LOW).
