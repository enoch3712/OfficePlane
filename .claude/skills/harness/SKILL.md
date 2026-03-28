---
name: harness
description: Improve and maintain the agent harness itself — hooks, checks, agents, skills, scripts.
argument-hint: [what to improve]
---

Maintain the OfficePlane agent harness. Use when the harness itself needs updates.

## Harness Components

| Component | Location | Purpose |
|-----------|----------|---------|
| Quality gate | `.claude/hooks/quality-gate.sh` | PostToolUse + Stop hooks — tracks dirty/reviewed markers |
| Session start | `.claude/hooks/session-start.sh` | Context primer for new sessions |
| Settings | `.claude/settings.json` | Hook wiring and permissions |
| Config | `harness.config.sh` | Project-specific values (slug, dirs, commands) |
| Agents | `.claude/agents/` | 5 specialist reviewers |
| Skills | `.claude/skills/` | /dev-loop, /validate, /review-*, /entropy-sweep |
| Scripts | `scripts/check-all.sh` | Unified quality pipeline |
| Pre-commit | `.githooks/pre-commit` | Git pre-commit hook |
| Checks | `checks/` | Python AST-based enforcement checks |

## When to update

- New module added -> update arch-guardian rules
- New endpoint pattern -> update security-auditor rules
- New UI pattern -> update ui-guardian rules
- New check needed -> add to `checks/` and register in `__main__.py`
- Quality gate logic change -> update `quality-gate.sh`
- New tool permission needed -> update `settings.json`

## Process

1. Read the component that needs updating
2. Make the change
3. Test: ensure hooks still work, checks still pass
4. Update this skill or CLAUDE.md if the change affects the workflow
