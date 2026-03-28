# Claude Code Subagents & Agent Teams Reference

> Subagents: https://code.claude.com/docs/en/sub-agents
> Agent Teams: https://code.claude.com/docs/en/agent-teams

---

## Subagents

Subagents run in isolated context windows with custom system prompts and tool
restrictions. They are the primary mechanism for specialized, domain-focused review
and analysis in a harness.

### Subagent file format

```markdown
---
name: my-reviewer
description: Reviews X for Y. Use when Z.
tools: Read, Grep, Glob, Bash
model: claude-opus-4-5          # optional — inherits session model if omitted
permissions:
  allow:
    - Bash(git diff*)
  deny:
    - Edit
    - Write
memory: project                  # none | project | user | cli
---

Full system prompt here. This is what Claude sees as its persona and instructions.
```

### Supported frontmatter fields

| Field | Values | Notes |
|-------|--------|-------|
| `name` | string | Must match filename (without .md) |
| `description` | string | Used by main Claude to decide when to delegate |
| `tools` | comma-separated | Restricts available tools |
| `model` | model ID | Defaults to session model |
| `permissions.allow` | list of tool patterns | Additive to base permissions |
| `permissions.deny` | list of tool patterns | Overrides allow |
| `memory` | `none` \| `project` \| `user` \| `cli` | Persistent memory scope |
| `isolation` | `worktree` | Runs in a fresh git worktree |

### Tool restriction patterns

```yaml
tools: Read, Grep, Glob, Bash, Edit, Write   # explicit list
permissions:
  allow:
    - Bash(git log*)      # allow only git log commands
    - Bash(uv run pytest*)
  deny:
    - Edit                # no file editing
    - Write               # no file creation
```

### Scopes (where subagent files live)

| Scope | Location | Visibility |
|-------|----------|------------|
| Project | `.claude/agents/*.md` | This project only |
| User | `~/.claude/agents/*.md` | All projects for this user |
| CLI plugin | `<plugin>/agents/*.md` | Installed plugin |

### Memory by scope

| Value | Storage location | Shared across |
|-------|-----------------|---------------|
| `none` | Not persisted | Nothing |
| `project` | `.claude/agent-memory/<agent>/` | All sessions in this project |
| `user` | `~/.claude/agent-memory/<agent>/` | All projects for this user |
| `cli` | In-process only | Current session |

### Built-in subagents (always available)

| Name | Purpose |
|------|---------|
| `general-purpose` | Research, multi-step tasks, open-ended search |
| `Explore` | Fast codebase exploration (no Edit/Write) |
| `Plan` | Architecture planning, implementation strategy |

### Defining hooks inside a subagent

Subagents can have their own hooks scoped to their operation:

```markdown
---
name: code-reviewer
hooks:
  Stop:
    - type: command
      command: echo "Review complete" >> /tmp/review-log.txt
---
```

### Foreground vs background invocation

```
# Foreground — main agent waits for result
Agent tool with run_in_background: false (default)

# Background — main agent continues, notified on completion
Agent tool with run_in_background: true
```

Use background for independent parallel work (e.g. run 3 reviewers simultaneously).
Use foreground when the result informs the next step.

### Choosing subagent vs main conversation

| Use subagent when | Use main conversation when |
|-------------------|-----------------------------|
| Task needs isolated context | Task needs full project context |
| Domain is specialized (security, FSD, etc.) | Task is cross-cutting |
| You want to run multiple in parallel | Sequential dependency on prior steps |
| Task is read-only review | Task involves editing files |
| Protecting main context from large outputs | Output directly informs next action |

---

## Agent Teams

Agent teams coordinate multiple Claude Code instances working in parallel with shared
task lists and direct inter-agent messaging.

> **Status:** Experimental feature — enable with `--dangerously-allow-agent-teams`

### When to use teams vs subagents

| | Subagents | Agent Teams |
|--|-----------|-------------|
| Context | Isolated | Separate full sessions |
| Communication | Return value only | Real-time messaging |
| Parallelism | Via `run_in_background` | Native, concurrent sessions |
| State sharing | None | Shared task list |
| Best for | Focused review tasks | Long-running parallel workstreams |

### Starting a team

```bash
claude --dangerously-allow-agent-teams
```

In the session:
```
/team create backend-team
/team create frontend-team
```

### Task assignment

```
# Assign to specific teammate
/task assign @backend-team "Implement the auth middleware"
/task assign @frontend-team "Build the login form"

# Broadcast to all
/task broadcast "Update CHANGELOG.md when your work is done"
```

### Communication

```
# Direct message
/message @backend-team "Are you using JWT or session tokens?"

# Check teammate status
/team status
```

### Quality gates for teams

```
# Require plan approval before execution
/team set-mode plan-approval

# Each teammate must pass review before merging
/task require-review @backend-team
```

### Architecture

- Each teammate is a separate Claude Code session with its own context
- Teams share a task list (visible to all members)
- Teammates can read/write shared files (coordinate to avoid conflicts)
- Token usage: each teammate consumes its own tokens independently

### Best practices

1. **Scope tasks to avoid file conflicts** — assign disjoint file sets to teammates
2. **Keep teams small** — 2-4 teammates; larger teams create coordination overhead
3. **Size tasks for 1-2 context windows** — teams don't help if one task is too large
4. **Provide full context upfront** — teammates can't ask the user for clarification
5. **Use for parallel independent work** — not sequential pipelines (subagents are better)

### Example: parallel code review

```
# Main agent assigns each review domain to a specialist
/task assign @arch-guardian "Review src/ for hexagonal architecture compliance"
/task assign @security-auditor "Review src/ for OWASP Top 10 issues"
/task assign @test-inspector "Review tests/ for coverage completeness"

# Wait for all to complete, then aggregate
/team wait-all
/task collect-results
```

### Known limitations

- Session resumption across restarts not yet supported
- Task status may lag by 1-2 tool calls
- Shutdown timing can leave orphaned sessions
- Requires pane/terminal support (does not work in headless mode)
