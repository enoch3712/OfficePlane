# Claude Code Platform Reference

> Settings:          https://code.claude.com/docs/en/settings
> Status line:       https://code.claude.com/docs/en/statusline
> Monitoring (OTel): https://code.claude.com/docs/en/monitoring-usage
> Headless / SDK:    https://code.claude.com/docs/en/headless
> Scheduled tasks:   https://code.claude.com/docs/en/scheduled-tasks
> Features overview: https://code.claude.com/docs/en/features-overview

---

## Settings & Configuration

### Configuration scopes (highest → lowest precedence)

| Scope | File | Git-committed | Who controls |
|-------|------|---------------|--------------|
| Managed | `/etc/claude-code/managed-settings.json` | No | Org admin — cannot be overridden |
| User | `~/.claude/settings.json` | No | Individual developer |
| Project | `.claude/settings.json` | Yes | Team (shared) |
| Local | `.claude/settings.local.json` | No | Developer override of project settings |

Later scopes override earlier ones, except **Managed** which always wins.

### Key settings fields

```json
{
  "model": "claude-opus-4-6",
  "theme": "dark",
  "permissions": {
    "allow": ["Bash(git *)", "Bash(docker compose *)"],
    "deny": ["Bash(rm -rf *)"]
  },
  "hooks": { ... },
  "env": {
    "MY_VAR": "value"
  },
  "autoMemory": true,
  "preferredNotifChannel": "terminal"
}
```

### Permission patterns

```json
"permissions": {
  "allow": [
    "Bash(git *)",                    // all git commands
    "Bash(docker compose *)",         // all docker compose commands
    "Bash(uv run *)",                 // all uv run commands
    "Edit(src/**)",                   // edit any file under src/
    "WebFetch(https://api.example*)"  // fetch specific domain
  ],
  "deny": [
    "Bash(rm -rf *)",
    "Bash(git push --force *)"
  ]
}
```

Patterns support glob syntax. `deny` takes precedence over `allow`.

### Environment variables in settings

```json
{
  "env": {
    "OTEL_EXPORTER_TYPE": "console",
    "ANTHROPIC_MODEL": "claude-opus-4-6",
    "UV_LINK_MODE": "copy"
  }
}
```

Variables set in `settings.json` are available to hooks and Claude's shell environment.

---

## Status Line

Configure a custom status bar at the bottom of Claude Code showing session metrics.

### Setup

```bash
/statusline setup    # interactive setup via Claude Code
```

Or manually set `statusline` in settings.json:

```json
{
  "statusline": {
    "command": "bash $CLAUDE_PROJECT_DIR/.claude/hooks/statusline.sh"
  }
}
```

### Available data (JSON piped to your script via stdin)

```json
{
  "model": "claude-opus-4-6",
  "context": {
    "used": 45230,
    "total": 200000,
    "percent": 22.6
  },
  "cost": {
    "session": 0.42,
    "currency": "USD"
  },
  "rateLimits": {
    "requestsRemaining": 48,
    "requestsLimit": 50,
    "resetAt": "2026-03-26T15:00:00Z"
  },
  "session": {
    "id": "abc123",
    "startedAt": "2026-03-26T14:30:00Z"
  }
}
```

### Example: context + cost display

```bash
#!/bin/bash
# Reads JSON from stdin, outputs status line string
DATA=$(cat)
PCT=$(echo "$DATA" | jq -r '.context.percent | floor')
COST=$(echo "$DATA" | jq -r '.cost.session')

if [ "$PCT" -gt 75 ]; then COLOR="\033[0;31m"    # red
elif [ "$PCT" -gt 50 ]; then COLOR="\033[0;33m"  # yellow
else COLOR="\033[0;32m"                           # green
fi

echo -e "${COLOR}ctx: ${PCT}%\033[0m | \$${COST}"
```

### Example: show GSD enforcement markers

```bash
#!/bin/bash
MARKERS=""
[ -f /tmp/.claude-dirty-$(basename $CLAUDE_PROJECT_DIR) ] && MARKERS="${MARKERS}⚠ dirty "
[ -f /tmp/.claude-changed-$(basename $CLAUDE_PROJECT_DIR) ] && MARKERS="${MARKERS}✎ changed "
[ -f /tmp/.claude-reviewed-$(basename $CLAUDE_PROJECT_DIR) ] || MARKERS="${MARKERS}☐ unreviewed"
echo "$MARKERS"
```

---

## Monitoring (OpenTelemetry)

Claude Code itself emits OTel telemetry about session activity — separate from
instrumenting your application.

### Quick start

```bash
export CLAUDE_CODE_ENABLE_TELEMETRY=1
export OTEL_METRICS_EXPORTER=otlp
export OTEL_LOGS_EXPORTER=otlp
export OTEL_EXPORTER_OTLP_ENDPOINT=http://localhost:4318
```

Or via managed settings for org-wide deployment:

```json
{
  "env": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "1",
    "OTEL_METRICS_EXPORTER": "console",
    "OTEL_LOGS_EXPORTER": "console"
  }
}
```

### Available metrics

| Metric | What it tracks |
|--------|---------------|
| `claude_code.session.count` | Number of sessions started |
| `claude_code.lines_of_code.count` | Lines added/removed |
| `claude_code.pull_request.count` | PRs created |
| `claude_code.commit.count` | Git commits made |
| `claude_code.cost.usage` | API cost in USD |
| `claude_code.token.usage` | Input/output/cache tokens |
| `claude_code.tool.use.count` | Per-tool invocation counts |
| `claude_code.api_request.count` | Total API requests |
| `claude_code.code_edit_tool.decision` | Accept/reject rate of edits |

### Event types (logs)

| Event | When emitted |
|-------|-------------|
| `user_prompt` | User sends a message |
| `assistant_response` | Claude responds |
| `tool_result` | Tool call completes |
| `api_request` | Anthropic API call |
| `api_error` | API error |

### Standard attributes on all events

```
claude_code.session_id       — correlates all events in a session
claude_code.model            — model used
claude_code.project_path     — project directory hash (privacy-safe)
claude_code.version          — Claude Code version
```

### Multi-team support

Use dynamic headers to route telemetry per team:

```json
{
  "env": {
    "OTEL_EXPORTER_OTLP_HEADERS": "x-team-id=backend-team,x-env=production"
  }
}
```

---

## Headless / Agent SDK

Run Claude Code programmatically without the interactive UI.

### Basic usage

```bash
claude -p "Fix the failing test in tests/test_auth.py"
```

### Structured JSON output

```bash
claude -p "List all API endpoints" --output-format json
```

### Stream JSON (for real-time processing)

```bash
claude -p "Refactor the auth module" --output-format stream-json | jq '.content'
```

### Bare mode (faster startup, no hooks/skills/MCP auto-discovery)

```bash
claude --bare -p "Quick check: does src/api/v1/endpoints/auth.py import from domain?"
```

### Auto-approve tools (CI/CD use)

```bash
claude -p "Run the test suite and fix any failures" \
  --allow-tool Bash \
  --allow-tool Edit \
  --allow-tool Write
```

### System prompt customization

```bash
claude -p "Review this code" \
  --system "You are a security auditor. Focus only on OWASP Top 10."
```

### Continue / resume sessions

```bash
# Continue most recent session
claude --continue -p "Now fix the issues you found"

# Resume specific session
claude --resume <session-id> -p "Continue from where we left off"
```

### CI/CD pattern

```bash
#!/bin/bash
# Run in CI — non-interactive, structured output, specific permissions
claude --bare \
  --allow-tool Bash \
  --allow-tool Read \
  --output-format json \
  -p "Run: uv run pytest tests/ --tb=short. Return a JSON summary of failures."
```

---

## Scheduled Tasks

Session-scoped recurring tasks using `/loop` and cron syntax.

### `/loop` command

```
/loop 5m Check if the build is passing and report status
/loop 10m /review-all
/loop 1h Run the test suite and summarize new failures
```

Intervals: `30s`, `5m`, `1h`, `2h`, etc.

### One-time reminders

```
/loop remind me in 30 minutes to run the migration
/loop at 3pm check if the deploy finished
```

### Managing tasks

```
/loop list      # show all scheduled tasks
/loop cancel 3  # cancel task #3
/loop cancel    # cancel all
```

### How it works

- Tasks run inside the current session — they share your context
- Jitter is applied (±10%) to prevent thundering herd
- Tasks expire after 3 days automatically
- Session exit cancels all tasks

### Cron expression reference

```
* * * * *
│ │ │ │ └── day of week (0-6, Sun=0)
│ │ │ └──── month (1-12)
│ │ └────── day of month (1-31)
│ └──────── hour (0-23)
└────────── minute (0-59)

Examples:
0 9 * * 1-5    → weekdays at 9am
*/15 * * * *   → every 15 minutes
0 0 * * *      → daily at midnight
```

### Comparison: session vs Cloud vs Desktop scheduling

| | Session `/loop` | Cloud scheduled | Desktop scheduled |
|--|-----------------|-----------------|-------------------|
| Persistence | Session only | Permanent | Permanent |
| Setup | Instant | API/dashboard | Settings UI |
| Context | Current session | Fresh session | Fresh session |
| Best for | Polling, reminders | Nightly jobs | Regular workflows |

---

## Features Overview — Extension Points

> Full reference: https://code.claude.com/docs/en/features-overview

### Extension layers (lowest → highest specificity)

| Layer | What it is | Best for |
|-------|-----------|----------|
| `CLAUDE.md` | Project instructions loaded into context | Conventions, architecture rules, workflows |
| Skills | Reusable prompts invoked with `/skill-name` | Repeatable workflows, domain procedures |
| MCP servers | External tool providers | APIs, databases, third-party services |
| Subagents | Isolated specialists with custom tools | Domain review, parallel analysis |
| Agent Teams | Parallel Claude sessions | Long-running parallel workstreams |
| Hooks | Shell commands at lifecycle events | Enforcement, auto-format, state machines |
| Plugins | Packaged bundles (agents + skills + MCP) | Distributable harness components |

### Choosing between extensions

**Skill vs Subagent:**
- Use a **Skill** when the task needs main conversation context and you want a reusable prompt template
- Use a **Subagent** when the task needs isolation, tool restrictions, or domain specialization

**CLAUDE.md vs Skill:**
- Use **CLAUDE.md** for always-on project conventions (loaded every session)
- Use a **Skill** for on-demand workflows (only loaded when invoked)

**Subagent vs Agent Team:**
- Use a **Subagent** for focused single-domain tasks (review, analysis)
- Use an **Agent Team** for parallel independent workstreams that need coordination

**MCP vs Skill:**
- Use **MCP** to expose external tools (APIs, databases) as first-class tools
- Use a **Skill** for prompt-based workflows that don't need new tool types

### Context cost by feature

| Feature | Context cost | Notes |
|---------|-------------|-------|
| CLAUDE.md | ~2-5k tokens always | Loaded every session |
| Skill | ~1-3k tokens on invoke | Only when used |
| MCP tool definition | ~200 tokens/tool always | All tools in context |
| Subagent | 0 tokens in main context | Isolated window |
| Hook | 0 tokens | Shell, not context |

### Combining features (harness pattern)

```
CLAUDE.md              ← project conventions (always loaded)
  + Skills             ← dev-loop, validate, review-all (on demand)
    + Subagents        ← arch, security, ddd, fsd, test reviewers (isolated)
      + Hooks          ← auto-format, markers, stop gate (automatic)
        + MCP          ← external services if needed
```
