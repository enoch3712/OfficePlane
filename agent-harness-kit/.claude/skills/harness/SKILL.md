---
name: harness
description: Improve and maintain the agent harness — hooks, checks, skills, agents, contracts, enforcement architecture. Use when adding rules, fixing enforcement gaps, or auditing harness compliance.
argument-hint: [what to improve or audit]
---

Improve, maintain, or audit the agent harness — the 3-layer enforcement system that keeps agents productive, safe, and sharp.

## Reference Docs

Read these before making changes:

- `@docs/design/enforcement-architecture.md` — the 3-layer model (hooks, pre-commit, agent reviews)
- `@docs/design/core-beliefs.md` — team taste, promotion ladder (doc → lint → code)
- `@docs/references/harness-engineering-openai.md` — the 6 principles we follow
- `@docs/exec-plans/tech-debt-tracker.md` — open enforcement gaps

## The 3 Enforcement Layers

```
Layer 1: Claude Code Hooks     (.claude/hooks/quality-gate.sh, .claude/settings.json)
Layer 2: Git Pre-Commit        (.githooks/pre-commit → scripts/check-all.sh → checks/)
Layer 3: Agent Review Loop     (.claude/agents/*.md, .claude/skills/dev-loop/SKILL.md)
```

## Key Files

| File | What it does |
|------|-------------|
| `.claude/hooks/quality-gate.sh` | 7-marker state machine: dirty, changed, fe-dirty, fe-changed, reviewed, test contract, doc contract |
| `.claude/hooks/session-start.sh` | Session context primer: git, Docker, markers, tech debt, plans |
| `.claude/settings.json` | Hook configuration (PostToolUse, Stop events) |
| `agent_builder_backend/checks/` | 34 AST rules across 9 modules (run `--list-rules` for all) |
| `scripts/check-fsd.sh` | 3 FSD rules for frontend (FSD-001/002/003) |
| `scripts/check-all.sh` | Unified quality gate (backend + frontend + docs) |
| `.claude/skills/dev-loop/SKILL.md` | The full loop: test plan → validate → test → review → improve |
| `.claude/agents/*.md` | 6 subagents (arch, security, ddd, fsd, test, entropy) |
| `docs/design/enforcement-architecture.md` | Documents the full model |

## When to Use This Skill

- Adding a new mechanical rule to `checks/`
- Adding or modifying a hook in `quality-gate.sh`
- Creating or upgrading a subagent in `.claude/agents/`
- Creating or modifying a skill in `.claude/skills/`
- Fixing an enforcement gap identified in an audit or review
- Promoting a pattern from doc → lint → mechanical check
- Running a compliance audit against the OpenAI reference

## Process: Adding a New Rule

### 1. Identify the invariant

What's the rule? Is it mechanical (clear right/wrong) or taste-based (requires judgment)?

- **Mechanical** → add to `checks/` (backend) or `check-fsd.sh` (frontend)
- **Taste-based** → add to a subagent's rules list in `.claude/agents/`
- **Both** → mechanical check for the clear cases, subagent for the nuanced cases

### 2. Follow the promotion ladder

```
Document (core-beliefs.md) → Lint/Remind (advisory warning) → Enforce (hard failure)
```

New rules start as advisory warnings. Once pre-existing violations are fixed, promote to hard failure. Track the promotion in `core-beliefs.md` promotion log.

### 3. Implement

**For a new AST check:**
1. Create `agent_builder_backend/checks/{name}.py` following the existing pattern
2. Define `name`, `description`, `rules` at module level
3. Implement `run(*, src_root: str) -> CheckResult`
4. Add `import checks.{name}` to `checks/__main__.py`
5. Verify: `docker compose exec -T backend uv run python -m checks --check={name}`
6. Verify meta: `docker compose exec -T backend uv run python -m checks --check=meta`

**For a new FSD check:**
1. Add the rule to `scripts/check-fsd.sh`
2. Add `--json` support for the new rule
3. Verify: `bash scripts/check-fsd.sh`

**For a new hook behavior:**
1. Edit `.claude/hooks/quality-gate.sh`
2. Add to the appropriate action (`mark-edit`, `check-bash`, or `stop-gate`)
3. Validate syntax: `bash -n .claude/hooks/quality-gate.sh`
4. Update header comments to document the new behavior

**For a new subagent rule:**
1. Edit `.claude/agents/{agent}.md`
2. Add the rule to the numbered list with clear PASS/FAIL criteria
3. If the agent needs memory, ensure `.claude/agent-memory/{agent}/MEMORY.md` exists

**For a new mechanical reminder:**
1. Add to the stop-gate section of `quality-gate.sh` (after the blocking checks)
2. Use `echo "Reminder: ..." >&2` — do NOT `exit 2` (reminders don't block)

### 4. Update docs

Always update after harness changes:
- `docs/design/enforcement-architecture.md` — marker table, flow diagram, rule counts
- `CLAUDE.md` — if skills/agents table or hooks section changed
- `docs/design/core-beliefs.md` — if a belief was promoted to code

Run `./scripts/check-docs.sh` to verify links.

### 5. Review

Run `/review-security` on hook changes (bash scripts are security-sensitive).
Run `/review-all` on subagent/skill changes.

## Process: Auditing Harness Compliance

### Against the OpenAI 6 Principles

1. **Map, Not Manual** — Is CLAUDE.md under 150 lines? Are removed sections @-referenced?
2. **Repository Knowledge = System of Record** — Is everything in the repo? No tacit knowledge?
3. **Agent Legibility > Human Readability** — `--json` output? Error messages with fixes? Structured logging?
4. **Enforce Invariants, Not Implementations** — Rigid boundaries, flexible interiors?
5. **Agent-to-Agent Review Loop** — `/dev-loop` runs all reviewers? FAIL blocks exit?
6. **Entropy Management** — Promotion ladder working? ENTROPY-STALE catching drift?

### Coverage audit

For each belief in `core-beliefs.md`, check:
- Is it documented? (always yes — it's in the file)
- Is it mechanically enforced? (check `checks/`, `check-fsd.sh`, hooks)
- Is it agent-enforced? (check subagent rules)
- Is it only a reminder? (check stop-gate reminders)
- Is it unenforced? (**gap** — should be at least a reminder)

### Symmetry audit

Compare backend vs. frontend enforcement. They should be symmetric:
- Mechanical rules: backend `checks/` vs. frontend `check-fsd.sh`
- Hook tracking: dirty/changed vs. fe-dirty/fe-changed
- Auto-format: ruff vs. prettier
- Subagent review: arch+security+ddd vs. fsd-guardian

## Process: Maintaining the Harness

### Weekly

- Run `/entropy-sweep` — ENTROPY-STALE catches doc references to deleted files
- Check `session-start.sh` output — are tech debt items accumulating?
- Check `score-history.csv` — is the quality score trending down?

### After major features

- Run the compliance audit (6 principles)
- Run the symmetry audit (backend vs. frontend)
- Check for new patterns that should be promoted to checks

### When a rule keeps getting violated

If the same violation appears in 3+ reviews:
1. Promote from subagent rule → mechanical check
2. Add to `checks/` or `check-fsd.sh`
3. Log the promotion in `core-beliefs.md`
4. Update the subagent to reference the mechanical check instead of duplicating it
