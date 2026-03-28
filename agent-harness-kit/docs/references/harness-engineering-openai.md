# Harness Engineering: Leveraging Codex in an Agent-First World

> **Source:** OpenAI Engineering Blog, February 11, 2026
> **Author:** Ryan Lopopolo, Member of the Technical Staff
> **Why saved:** Reference material for our agent-first development strategy

---

## Key Takeaways for Our Team

### 1. Map, Not Manual
- `AGENTS.md` should be ~100 lines — a table of contents, not an encyclopedia
- Deep knowledge lives in structured `docs/` with progressive disclosure
- Agents start with a small, stable entry point and are taught where to look next

### 2. Repository Knowledge = System of Record
- Slack discussions, Google Docs, tacit knowledge — if it's not in the repo, it doesn't exist for agents
- Plans are first-class artifacts (active, completed, tech-debt tracker)
- Dedicated linters and CI jobs validate the knowledge base is up to date

### 3. Agent Legibility > Human Readability
- Code is optimized first for agent comprehension
- Logs, metrics, traces exposed to agents via local observability stack
- App bootable per git worktree so agents can launch/drive one instance per change

### 4. Enforce Invariants, Not Implementations
- Rigid architectural layers with validated dependency directions
- Custom linters with error messages that inject remediation instructions into agent context
- "Taste invariants": structured logging, naming conventions, file size limits, reliability requirements

### 5. Agent-to-Agent Review Loop
- Agents review their own changes, request additional reviews, respond to feedback
- Human review optional — agent-to-agent review handles most cases
- "Ralph Wiggum Loop": iterate until all agent reviewers are satisfied

### 6. Entropy Management
- Agent replicates patterns that already exist — even bad ones
- "Doc-gardening" agent scans for stale documentation
- Capture human taste as documentation updates or encode directly into tooling
- When docs fall short, promote the rule into code (linter/CI)

---

## Architecture Pattern (from their codebase)

```
Business Domain
  Types → Config → Repo → Service → Runtime → UI
  (strict dependency direction, mechanically enforced)

Cross-cutting concerns enter through Providers only
Utils → Providers, Utils → Service
```

## Knowledge Base Layout (from their codebase)

```
docs/
├── design-docs/
│   ├── index.md
│   ├── core-beliefs.md
│   └── ...
├── exec-plans/
│   ├── active/
│   ├── completed/
│   └── tech-debt-tracker.md
├── generated/
│   └── db-schema.md
├── llms-txt/
│   ├── nixpacks-llms.txt
│   └── uv-llms.txt
├── DESIGN.md
├── FRONTEND.md
└── PLANS.md
```

## Metrics They Achieved

- ~1,500 PRs merged over 5 months (3 engineers initially, grew to 7)
- 3.5 PRs per engineer per day (throughput increased with team size)
- ~1 million lines of code
- Single Codex runs working 6+ hours on complex tasks
- 0 lines of manually-written code (hard constraint)
