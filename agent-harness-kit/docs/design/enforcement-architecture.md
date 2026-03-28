# Enforcement Architecture

> How quality is enforced across the development loop — from real-time hooks to pre-commit to agent reviews.

Inspired by [Harness Engineering (OpenAI)](../references/harness-engineering-openai.md): enforce invariants, not implementations.

## Three Enforcement Layers

```
Layer 1: Claude Code Hooks (real-time, every tool use)
Layer 2: Git Pre-Commit (.githooks/pre-commit)
Layer 3: Agent Review Loop (/dev-loop, /review-all)
```

Each layer catches different classes of issues. Together they form a closed loop — you can't leave a session, commit, or merge without all layers passing.

---

## Layer 1: Claude Code Hooks

**Source:** `.claude/settings.json` → `.claude/hooks/quality-gate.sh`

Fires on every Edit, Write, and Bash tool use during a Claude session. Uses a 5-marker state machine:

| Marker | Set when | Cleared when | Purpose |
|--------|----------|--------------|---------|
| `dirty` | `.py` file edited | Quality checks run (ruff, ty, pytest, checks) | Code hasn't been validated |
| `changed` | `.py` file edited | Never (per session) | Code was modified at some point |
| `reviewed` | `/review-all` or `/dev-loop` completes | New `.py` edit (invalidates prior review) | Comprehensive agent review done |
| `contract` | `/dev-loop` Step 0d writes test contract | test-inspector checks off items as `- [x]` | Test coverage verified for critical paths |
| `doc-contract` | `/dev-loop` Step 0e writes doc contract | Step 5 checks off items as `- [x]` | Doc updates verified for changed code |

**Stop-gate logic:** Block session exit if `dirty` exists (quality not run) OR if `changed` exists without `reviewed` (reviews not run) OR if test contract exists with unchecked CRITICAL/HIGH items (test coverage gaps) OR if doc contract exists with unchecked HIGH items (doc updates missing). Missing contracts are a warning, not a block (allows harness-only changes and `/review-all` without Step 0). Additionally, emit a **doc freshness reminder** (warning, not block) if code was changed but no docs were updated.

**Auto-format:** Every `.py` edit triggers `ruff format` automatically — agents never leave unformatted code.

**Key design choices:**
- `changed` is monotonic (only set, never cleared) — so you can't skip reviews even after quality checks clear `dirty`
- `reviewed` is invalidated on any new edit — reviews must reflect the final code state
- `contract` is a file, not just a flag — the stop-gate greps it for unchecked `- [ ]` lines with CRITICAL/HIGH. test-inspector edits the file to check items off. This makes coverage verification **mechanical**: the hook doesn't trust the agent's word, it reads the artifact.
- `doc-contract` follows the same file-based pattern — the stop-gate greps for unchecked `- [ ]` lines with HIGH. Step 5 of `/dev-loop` verifies each doc update and checks items off. This prevents doc drift at the source.
- `docs-touched` tracks whether docs were updated alongside code — reminder only, not a block
- Markers persist in `/tmp/` across sessions — if you left dirty, you should know

---

## Layer 2: Git Pre-Commit

**Source:** `.githooks/pre-commit` → `scripts/check-all.sh`

Fires on `git commit`. Scoped to staged files — only runs checks relevant to what changed.

| Staged files | What runs |
|--------------|-----------|
| Backend `.py` | ruff check → ruff format → ty (advisory) → checks (advisory) → pytest |
| Frontend `.ts`/`.tsx` | tsc → eslint → build |
| Docs `.md` | Broken internal links, index completeness |
| Mixed | All applicable scopes |
| None of the above | Skip — no checks needed |

The pre-commit hook delegates to `scripts/check-all.sh` which is the same unified pipeline used by `/validate`.

**Bypass:** `git commit --no-verify` (not recommended).

---

## Layer 3: Agent Review Loop

**Source:** `.claude/agents/` (6 subagents) + `.claude/skills/` (review skills)

Specialized agents review code changes after mechanical checks pass. Each agent owns one quality domain:

| Agent | Domain | Reference |
|-------|--------|-----------|
| `arch-guardian` | Hexagonal architecture, DDD layers | `docs/adr/0006-ddd-hexagonal-architecture.md` |
| `security-auditor` | OWASP Top 10, auth patterns | `docs/exec-plans/tech-debt-tracker.md` |
| `ddd-solid-reviewer` | SOLID principles, domain modeling | `DOMAIN_LANGUAGE.md` |
| `fsd-guardian` | FSD layer imports, Colibri UI Kit | `docs/frontend/guidelines.md` |
| `test-inspector` | Test quality + coverage verification (test contract) | `docs/dev/testing.md` |
| `entropy-sweeper` | Duplication, drift, dead code (7 categories) | `docs/design/core-beliefs.md` |

All agents have full tool access (`Read, Grep, Glob, Bash, Edit, Write`). Reviewers produce reports — they do not fix code directly. The main agent or a follow-up agent acts on the findings.

**`/dev-loop`** is the standard workflow — it runs all three layers in sequence:
0. TEST PLAN + DOC PLAN (risk-based feature decomposition → test contract + doc contract)
1. VALIDATE (mechanical checks)
2. TEST (pytest, Newman, E2E verification)
3. REVIEW (relevant subagents in parallel — test-inspector verifies test contract)
4. IMPROVE (fix findings + write missing tests, loop back)
5. DOC CHECK (verify doc contract — update docs, check off items)
6. DONE (touch reviewed marker, report contract status)

**`/review-all`** runs only step 3 (all relevant reviewers).

Only `/dev-loop` and `/review-all` satisfy the review gate. Individual review skills (`/review-arch`, etc.) are for targeted investigation — they do not set the reviewed marker.

---

## How the Layers Connect

```
Claude edits .py
  → Hook: auto-format + set dirty + set changed + clear reviewed
    → Claude runs /dev-loop
      → Step 0: analyze diff → risk assessment → write test contract + doc contract
      → Step 1: ./scripts/check-all.sh → clears dirty
      → Step 2: pytest + E2E verification (check off [manual] items)
      → Step 3: subagents review + test-inspector verifies test contract
        → uncovered CRITICAL/HIGH? → FAIL → write tests → loop back
      → Step 5: verify doc contract → update docs → check off items
        → uncovered HIGH? → FAIL → update docs → loop back
      → Step 6: scorecard (--fast, only if tests passed)
      → Step 7: touch reviewed marker + report contract status
        → Stop hook: dirty=no, changed=yes, reviewed=yes, contracts satisfied → PASS
          → git commit
            → Pre-commit: check-all.sh (scoped to staged files) → PASS
```

If any layer fails, the loop forces remediation before proceeding.

---

## File Reference

| File | Purpose |
|------|---------|
| `.claude/settings.json` | Hook configuration (which tool events trigger which actions) |
| `.claude/hooks/quality-gate.sh` | 3-marker state machine (mark-edit, check-bash, stop-gate) |
| `.githooks/pre-commit` | Git pre-commit hook (scopes checks to staged files) |
| `scripts/check-all.sh` | Unified quality pipeline (backend + frontend) |
| `scripts/setup-hooks.sh` | Configures git to use `.githooks/` |
| `.claude/agents/*.md` | Subagent prompts (architecture, security, DDD, FSD, tests, entropy) |
| `.claude/skills/dev-loop/SKILL.md` | Full develop-validate-test-review-improve loop |
| `.claude/skills/review-all/SKILL.md` | Run all relevant reviewers and aggregate |
| `scripts/check-docs.sh` | Doc quality checks (broken links, index completeness) |
| `scripts/generate-scorecard.sh` | Quality scorecard: mechanical metrics + Opus agent analysis |
| `docs/generated/quality-scorecard.md` | Current codebase health (read at session start) |
| `docs/generated/score-history.csv` | Metrics over time for trend analysis |
| `agent_builder_backend/checks/` | AST-based mechanical checks (29 rules, `--json` output) |
| `docs/generated/enforcement-rules.md` | Auto-generated rule reference |

---

## Related

- [Core Beliefs](core-beliefs.md) — the taste rules that enforcement encodes
- [Harness Engineering (OpenAI)](../references/harness-engineering-openai.md) — the reference playbook
- [Review Process](../review/REVIEW-PROCESS.md) — step-by-step review loop details
- [EP003: Architecture Enforcement](../exec-plans/active/EP003-architecture-taste-enforcement.md)
- [EP004: Agent Review Loop](../exec-plans/active/EP004-agent-review-loop.md)
