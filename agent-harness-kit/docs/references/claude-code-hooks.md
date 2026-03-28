# Claude Code Hooks Reference

> Official docs: https://code.claude.com/docs/en/hooks

Hooks are user-defined shell commands, HTTP endpoints, LLM prompts, or subagents that
execute automatically at specific lifecycle points in Claude Code. The primary enforcement
layer of any harness.

---

## Hook Types

| Type | What it runs | Best for |
|------|--------------|----------|
| `command` | Shell command | Fast checks, file formatting, markers |
| `http` | HTTP POST to an endpoint | Remote enforcement, audit logs |
| `prompt` | LLM prompt | Nuanced judgment calls |
| `agent` | Subagent (full Claude context) | Complex analysis, code review |

---

## Hook Events

| Event | When it fires | Common uses |
|-------|---------------|-------------|
| `PreToolUse` | Before any tool call | Block destructive commands, validate before edit |
| `PostToolUse` | After any tool call | Auto-format, set markers, audit log |
| `Stop` | Before Claude stops responding | Quality gate — block exit if invariants broken |
| `SubagentStop` | Subagent completes | Aggregate subagent results |
| `PreCompact` | Before context compaction | Save state before context reset |
| `SessionStart` | Session begins (new feature) | Load context, check service health |
| `Notification` | Claude sends a notification | Route alerts |

---

## Configuration (settings.json)

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "bash $CLAUDE_PROJECT_DIR/.claude/hooks/quality-gate.sh mark-edit $CLAUDE_TOOL_INPUT_FILE_PATH"
          }
        ]
      }
    ],
    "Stop": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "bash $CLAUDE_PROJECT_DIR/.claude/hooks/quality-gate.sh stop-gate"
          }
        ]
      }
    ]
  }
}
```

Configuration scopes (highest to lowest precedence):
- **Local** (`~/.claude/projects/<project>/settings.local.json`) — per-project, git-ignored
- **Project** (`.claude/settings.json`) — committed, shared with team
- **User** (`~/.claude/settings.json`) — all projects for this user
- **Managed** (`/etc/claude-code/managed-settings.json`) — org-level, cannot be overridden

---

## Environment Variables Available in Hooks

| Variable | Value |
|----------|-------|
| `CLAUDE_PROJECT_DIR` | Absolute path to project root |
| `CLAUDE_TOOL_NAME` | Tool being used (e.g., `Edit`, `Bash`) |
| `CLAUDE_TOOL_INPUT_FILE_PATH` | File path for Edit/Write/Read tools |
| `CLAUDE_TOOL_INPUT_COMMAND` | Command string for Bash tool |
| `CLAUDE_HOOK_EVENT` | Event type (`PostToolUse`, `Stop`, etc.) |
| `CLAUDE_SESSION_ID` | Current session ID |
| `CLAUDE_TOOL_RESPONSE` | (PostToolUse) Tool result JSON |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| `0` | Success — continue normally |
| `1` | Warning — show stderr to Claude, continue |
| `2` | Block — abort the operation, show stderr to Claude |

**For Stop hooks:** exit `2` blocks Claude from stopping. Claude reads stderr as the
reason — **write stderr like a prompt**: "Run `X` to fix `Y`." Claude will act on it.

---

## Matcher Patterns

```json
"matcher": "Edit|Write"           // tool name regex (OR logic)
"matcher": "Bash"                 // exact tool name
"matcher": ""                     // matches all events
"matcher": ".*\\.py$"             // file path regex (for file-based tools)
```

For `PostToolUse`, matcher runs against the tool name. For file-path filtering,
use conditional logic inside the hook script.

---

## Key Patterns for Harness Engineering

### 1. Marker state machine (set/clear via PostToolUse + Stop)

```bash
# PostToolUse: mark dirty on any .py edit
if [[ "$CLAUDE_TOOL_INPUT_FILE_PATH" == *.py ]]; then
  touch /tmp/.dirty-marker
fi

# Stop: block if dirty
if [ -f /tmp/.dirty-marker ]; then
  echo "Run quality checks before stopping." >&2
  exit 2
fi
```

### 2. Auto-format on every edit (PostToolUse)

```bash
if [[ "$CLAUDE_TOOL_INPUT_FILE_PATH" == *.py ]]; then
  ruff format "$CLAUDE_TOOL_INPUT_FILE_PATH"
fi
```

### 3. Blocking destructive Bash commands (PreToolUse)

```bash
COMMAND="$CLAUDE_TOOL_INPUT_COMMAND"
if echo "$COMMAND" | grep -qE 'rm -rf|DROP TABLE|git push --force'; then
  echo "Blocked: destructive command requires explicit approval." >&2
  exit 2
fi
```

### 4. Prompt injection protection for planning files (PreToolUse)

```bash
if [[ "$CLAUDE_TOOL_INPUT_FILE_PATH" == */.planning/* ]]; then
  if grep -qiE 'ignore.*instructions|disregard|override.*system' "$CLAUDE_TOOL_INPUT_FILE_PATH" 2>/dev/null; then
    echo "Potential prompt injection detected in planning file." >&2
    exit 2
  fi
fi
```

### 5. Stop hook as quality gate — stderr is a prompt

```bash
# Claude reads this and acts on it immediately
echo "Backend code was modified but quality checks were not run." >&2
echo "Run: docker compose exec -T backend uv run ruff check --fix ." >&2
exit 2
```

---

## Agent Hooks (type: agent)

Hooks can spawn a subagent instead of running a shell command. Useful for judgment
calls that need reasoning, not just pattern matching:

```json
{
  "type": "agent",
  "agent": "security-auditor",
  "prompt": "Review the code change at $CLAUDE_TOOL_INPUT_FILE_PATH for security issues."
}
```

The agent runs in its own context window. If it exits with code 2, the operation
is blocked.

---

## Known Limitations / Gotchas

- `set -euo pipefail` with `grep -c` returning 0 matches exits 1, triggering `||`
  fallback and doubling the output. Use `|| true` instead of `|| echo 0` for count
  commands that may return 0 matches.
- `head -N` with more input than N lines causes SIGPIPE on the upstream command.
  With `pipefail`, this returns non-zero. Add `|| true` to the pipeline.
- The `!` prefix in Claude Code terminal input is logical NOT in bash — it negates
  exit codes. Don't use `!` to invoke hook scripts manually.
- `changed` marker should be monotonic (set-only, never cleared) — ensures reviews
  can't be skipped even after quality checks clear `dirty`.
- `reviewed` marker must be cleared on any new edit — reviews must reflect final state.
