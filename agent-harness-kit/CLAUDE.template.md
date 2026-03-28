# Agent Instructions

This is an **agent-first, harness-engineered codebase**. Agents are the primary developers — humans guide direction and taste. `/dev-loop` is the standard workflow. See @docs/design/core-beliefs.md for beliefs and @docs/design/enforcement-architecture.md for the 3-layer enforcement model.

## Preferred Stacks

- **Backend:** {{BACKEND_STACK}}
- **Frontend:** {{FRONTEND_STACK}}

## Project Structure

```
{{BACKEND_DIR}}/
├── checks/                # Mechanical enforcement (python -m checks)
└── src/                   # api/, application/, domain/, infrastructure/
{{FRONTEND_DIR}}/
└── src/                   # app/, pages/, widgets/, features/, entities/, shared/
.claude/
├── agents/                # Specialized review subagents
├── hooks/                 # quality-gate.sh, session-start.sh
├── skills/                # /dev-loop, /validate, /review-*, /setup-harness
└── settings.json
scripts/
├── check-all.sh           # Unified quality pipeline
├── check-fsd.sh           # FSD layer enforcement
├── setup-hooks.sh         # Install git pre-commit hook
└── package-harness.sh     # Package the harness as a zip
harness.config.sh          # Project-specific harness config (slug, dirs, commands)
docs/
├── design/                # core-beliefs.md, enforcement-architecture.md
├── adr/                   # Architecture Decision Records
└── dev/                   # setup.md, testing.md
CLAUDE.md
```

## Quick Start

```bash
./scripts/setup-hooks.sh   # install git pre-commit hook (once after clone)
./scripts/dev.sh           # start all services
```

See @docs/dev/setup.md for prerequisites and credentials.

---

## Quality Checklist

```bash
./scripts/check-all.sh              # all checks (backend + frontend + docs)
./scripts/check-all.sh backend      # backend only
./scripts/check-all.sh frontend     # frontend only
```

Pipeline: ruff check → ruff format → ty (advisory) → checks (advisory) → pytest → tsc → eslint → build.

---

## Code Style

- **Named arguments required** — enforce with `*` in signatures.
- **Trailing commas** in all multi-line collections.
- **Type hints everywhere** — modern syntax (`list[int]`, not `List[int]`).
- **Google-style docstrings.** No obvious comments.

See @docs/design/core-beliefs.md for full conventions.

---

## Skills & Subagents

### Skills (invoke with `/skill-name`)

| Skill | Purpose |
|-------|---------|
| `/validate` | Quality gate: ruff + ty + checks |
| `/dev-loop` | Full loop: validate → test → review → improve (max 5 iterations) |
| `/entropy-sweep` | Detect and fix code drift |
| `/harness` | Improve and maintain the harness |
| `/review-arch` | Architecture review |
| `/review-security` | Security review |
| `/review-ddd` | DDD/SOLID review |
| `/review-fsd` | FSD review |
| `/review-tests` | Test quality review |
| `/review-all` | Run all relevant reviewers in parallel |
| `/setup-harness` | Reconfigure harness for this project |

### Subagents (`.claude/agents/`)

| Agent | Role |
|-------|------|
| `arch-guardian` | Hexagonal architecture compliance |
| `security-auditor` | OWASP Top 10, auth patterns, input validation |
| `ddd-solid-reviewer` | SOLID principles, domain modeling |
| `fsd-guardian` | FSD layer imports, Colibri/UI kit usage |
| `test-inspector` | Test quality + coverage verification |
| `entropy-sweeper` | Anti-entropy: detect → classify → fix → verify |

### Hooks (`.claude/settings.json`)

- **PostToolUse:** Auto-formats `.py`; tracks backend/frontend dirty/changed/reviewed markers
- **Stop:** Quality gate — blocks if code changed without checks or reviews

**`/dev-loop` is the standard workflow.**
