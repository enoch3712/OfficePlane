#!/usr/bin/env bash
# Deterministic quality gate using a 3-marker pattern (backend + frontend).
#
# Three actions dispatched from .claude/settings.json hooks:
#   mark-edit   -> PostToolUse Edit|Write: mark dirty if .py/.ts/.tsx edited, auto-format .py
#   check-bash  -> PostToolUse Bash: mark dirty if .py/.ts/.tsx written via cp/mv, clear if quality check ran
#   stop-gate   -> Stop: block session if code is dirty OR reviews not run
#
# Backend marker files:
#   dirty   (/tmp/.claude-dirty-<slug>)      — cleared when quality checks run
#   changed (/tmp/.claude-changed-<slug>)    — never cleared (records code was touched)
#
# Frontend marker files:
#   fe-dirty   (/tmp/.claude-fe-dirty-<slug>)   — cleared when frontend checks run
#   fe-changed (/tmp/.claude-fe-changed-<slug>) — never cleared
#
# Shared marker files:
#   reviewed     (/tmp/.claude-reviewed-<slug>)     — set by /review-all or /dev-loop
#   docs-touched (/tmp/.claude-docs-touched-<slug>) — set when .md files edited

set -euo pipefail

# Load project config
CONFIG="${CLAUDE_PROJECT_DIR}/harness.config.sh"
if [ -f "$CONFIG" ]; then
  source "$CONFIG"
else
  echo "Warning: harness.config.sh not found — using defaults" >&2
  HARNESS_PROJECT_SLUG="officeplane"
  BACKEND_DIR="src"
  FRONTEND_DIR="ui"
  BACKEND_SERVICE="api"
  BACKEND_EXEC="docker compose exec -T api"
  BACKEND_RUN="docker compose exec -T api python -m"
fi

DIRTY="/tmp/.claude-dirty-${HARNESS_PROJECT_SLUG}"
CHANGED="/tmp/.claude-changed-${HARNESS_PROJECT_SLUG}"
FE_DIRTY="/tmp/.claude-fe-dirty-${HARNESS_PROJECT_SLUG}"
FE_CHANGED="/tmp/.claude-fe-changed-${HARNESS_PROJECT_SLUG}"
REVIEWED="/tmp/.claude-reviewed-${HARNESS_PROJECT_SLUG}"
DOCS_TOUCHED="/tmp/.claude-docs-touched-${HARNESS_PROJECT_SLUG}"
CONTRACT="/tmp/.test-contract-${HARNESS_PROJECT_SLUG}.md"
DOC_CONTRACT="/tmp/.doc-contract-${HARNESS_PROJECT_SLUG}.md"
ACTION="${1:-}"

case "$ACTION" in
  mark-edit)
    INPUT=$(cat)
    FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

    # Mark dirty + changed if any .py file was edited. Invalidate prior review.
    if [ -n "$FILE" ] && echo "$FILE" | grep -qE '\.py$'; then
      touch "$DIRTY"
      touch "$CHANGED"
      rm -f "$REVIEWED"
    fi

    # Mark fe-dirty + fe-changed if any .ts/.tsx file was edited. Invalidate prior review.
    if [ -n "$FILE" ] && echo "$FILE" | grep -qE '\.(ts|tsx)$'; then
      touch "$FE_DIRTY"
      touch "$FE_CHANGED"
      rm -f "$REVIEWED"
    fi

    # Track doc edits
    if [ -n "$FILE" ] && echo "$FILE" | grep -qE '(/docs/|CLAUDE\.md)'; then
      touch "$DOCS_TOUCHED"
    fi

    # Auto-format backend .py files with ruff (if available in container).
    if [ -n "$FILE" ] && echo "$FILE" | grep -q "${BACKEND_DIR}/.*\.py$"; then
      RELPATH=$(echo "$FILE" | sed "s|.*${BACKEND_DIR}/||")
      docker compose -f "$CLAUDE_PROJECT_DIR/docker-compose.yml" exec -T "${BACKEND_SERVICE}" \
        ruff format "$RELPATH" 2>/dev/null || true
    fi
    ;;

  check-bash)
    INPUT=$(cat)
    CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

    # Mark dirty if Bash copies/moves .py files
    if echo "$CMD" | grep -qE '(cp |mv ).*\.py'; then
      touch "$DIRTY"
      touch "$CHANGED"
      rm -f "$REVIEWED"
    fi

    # Mark fe-dirty if Bash copies/moves .ts/.tsx files
    if echo "$CMD" | grep -qE '(cp |mv ).*\.(ts|tsx)'; then
      touch "$FE_DIRTY"
      touch "$FE_CHANGED"
      rm -f "$REVIEWED"
    fi

    # Clear dirty if a backend quality check command was run.
    if echo "$CMD" | grep -qE '(ruff check|ruff format|pytest|python -m checks|python -m pytest)'; then
      rm -f "$DIRTY"
    fi

    # Clear fe-dirty if a frontend quality check command was run.
    if echo "$CMD" | grep -qE '(\btsc\b|eslint|npm run lint|npm run build|next build)'; then
      rm -f "$FE_DIRTY"
    fi
    ;;

  stop-gate)
    BLOCKED=false
    MSG=""

    if [ -f "$DIRTY" ]; then
      BLOCKED=true
      MSG+="Backend code was modified but quality checks were not run.
Run: docker compose exec -T api ruff check --fix src/ && docker compose exec -T api python -m pytest tests/ -x -q

"
    fi

    if [ -f "$FE_DIRTY" ]; then
      BLOCKED=true
      MSG+="Frontend code was modified but checks were not run.
Run: cd ui && npx tsc --noEmit && npm run lint

"
    fi

    if { [ -f "$CHANGED" ] || [ -f "$FE_CHANGED" ]; } && [ ! -f "$REVIEWED" ]; then
      BLOCKED=true
      MSG+="Code was modified but agent reviews have not run.
Run /review-all or /dev-loop to complete the review loop.
"
    fi

    # Test contract verification
    if { [ -f "$CHANGED" ] || [ -f "$FE_CHANGED" ]; } && [ -f "$REVIEWED" ]; then
      if [ -f "$CONTRACT" ] && grep -qE '\- \[ \].*\b(CRITICAL|HIGH)\b' "$CONTRACT" 2>/dev/null; then
        UNCOVERED=$(grep -cE '\- \[ \].*\b(CRITICAL|HIGH)\b' "$CONTRACT" 2>/dev/null || true)
        BLOCKED=true
        MSG+="Test contract has $UNCOVERED uncovered CRITICAL/HIGH items.
Write the missing tests and re-run /dev-loop to satisfy the contract.
See: $CONTRACT
"
      fi
    fi

    # Doc contract verification
    if { [ -f "$CHANGED" ] || [ -f "$FE_CHANGED" ]; } && [ -f "$REVIEWED" ]; then
      if [ -f "$DOC_CONTRACT" ] && grep -qE '\- \[ \].*\bHIGH\b' "$DOC_CONTRACT" 2>/dev/null; then
        DOC_UNCOVERED=$(grep -cE '\- \[ \].*\bHIGH\b' "$DOC_CONTRACT" 2>/dev/null || true)
        BLOCKED=true
        MSG+="Doc contract has $DOC_UNCOVERED uncovered HIGH items.
Update the docs and check them off.
See: $DOC_CONTRACT
"
      fi
    fi

    if [ "$BLOCKED" = true ]; then
      echo "$MSG" >&2
      exit 2
    fi

    # -- Non-blocking reminders --
    if { [ -f "$CHANGED" ] || [ -f "$FE_CHANGED" ]; } && [ ! -f "$DOCS_TOUCHED" ]; then
      echo "Reminder: code was modified but no docs were updated." >&2
      echo "Consider: CLAUDE.md, docs/, README." >&2
    fi

    echo "" >&2
    echo "Before you stop -- ask yourself:" >&2
    echo "  1. Is there remaining work I can do without human input?" >&2
    echo "  2. Did I verify my changes against the running system?" >&2
    echo "  3. Are there background agents still running that I should wait for?" >&2
    echo "If yes to any: keep going. If no: you're done." >&2
    ;;

  *)
    echo "Usage: quality-gate.sh {mark-edit|check-bash|stop-gate}" >&2
    exit 1
    ;;
esac
