#!/usr/bin/env bash
# Deterministic quality gate using a 3-marker pattern (backend + frontend).
#
# Three actions dispatched from .claude/settings.json hooks:
#   mark-edit   → PostToolUse Edit|Write: mark dirty if .py/.ts/.tsx edited, auto-format .py
#   check-bash  → PostToolUse Bash: mark dirty if .py/.ts/.tsx written via cp/mv, clear if quality check ran
#   stop-gate   → Stop: block session if code is dirty OR reviews not run
#
# Backend marker files:
#   dirty   (/tmp/.claude-dirty-<slug>)
#     - Set when .py files are modified
#     - Cleared when a backend quality check command runs (ruff check, ty check, pytest, python -m checks)
#
#   changed (/tmp/.claude-changed-<slug>)
#     - Set when .py files are modified (same trigger as dirty)
#     - Never cleared during a session — records that code was touched at all
#
# Frontend marker files:
#   fe-dirty   (/tmp/.claude-fe-dirty-<slug>)
#     - Set when .ts/.tsx files are modified
#     - Cleared when a frontend quality check command runs (tsc, eslint, npm run lint, npm run build)
#
#   fe-changed (/tmp/.claude-fe-changed-<slug>)
#     - Set when .ts/.tsx files are modified (same trigger as fe-dirty)
#     - Never cleared during a session — records that frontend code was touched at all
#
# Shared marker files:
#   reviewed (/tmp/.claude-reviewed-<slug>)
#     - Set by /review-all or /dev-loop skills after comprehensive agent review
#     - Cleared on any new .py or .ts/.tsx edit (invalidates prior review)
#
#   docs-touched (/tmp/.claude-docs-touched-<slug>)
#     - Set when .md files in docs/ or CLAUDE.md are edited
#     - Used by stop-gate to suppress the doc reminder when docs were updated
#
# Stop-gate logic:
#   Block if dirty exists (backend quality checks not run)
#   Block if fe-dirty exists (frontend quality checks not run)
#   Block if (changed OR fe-changed) exists AND reviewed does not (reviews not run)
#   Block if test contract exists with unchecked CRITICAL/HIGH items (tests missing)
#   Block if doc contract exists with unchecked HIGH items (docs missing)
#   Warn (not block) if changed+reviewed but no contract (harness-only or /review-all)
#   Warn (not block) if code changed but no docs were updated
#   Pass otherwise (no code changes, or fully validated + reviewed + contracts satisfied)
#
# Known gaps (accepted):
#   - Subagent edits may not trigger parent hooks
#   - Exotic Bash writes (heredoc, python generating .py/.ts) not detected

set -euo pipefail

# Load project config (provides HARNESS_PROJECT_SLUG, BACKEND_DIR, FRONTEND_DIR, BACKEND_SERVICE)
CONFIG="${CLAUDE_PROJECT_DIR}/harness.config.sh"
if [ -f "$CONFIG" ]; then
  # shellcheck source=../../harness.config.sh
  source "$CONFIG"
else
  echo "Warning: harness.config.sh not found at $CONFIG — using defaults" >&2
  HARNESS_PROJECT_SLUG="my-project"
  BACKEND_DIR="backend"
  FRONTEND_DIR="frontend"
  BACKEND_SERVICE="backend"
  BACKEND_RUN="docker compose exec -T ${BACKEND_SERVICE} uv run"
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
    # Called by PostToolUse on Edit|Write.
    # Stdin: JSON with tool_input.file_path
    INPUT=$(cat)
    FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

    # Mark dirty + changed if any .py file was edited. Invalidate prior review.
    # Contract is NOT invalidated here — it persists through the improve loop
    # (agent writes tests → contract items get checked off). A new /dev-loop
    # run (Step 0) recreates it from scratch.
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

    # Track doc edits (docs/, CLAUDE.md, AGENTS.md, DOMAIN_LANGUAGE.md).
    # Uses /docs/ (not ^docs/) to match both relative and absolute paths.
    if [ -n "$FILE" ] && echo "$FILE" | grep -qE '(/docs/|CLAUDE\.md|AGENTS\.md|DOMAIN_LANGUAGE\.md)'; then
      touch "$DOCS_TOUCHED"
    fi

    # Auto-format backend .py files with ruff.
    if [ -n "$FILE" ] && echo "$FILE" | grep -q "${BACKEND_DIR}/.*\.py$"; then
      RELPATH=$(echo "$FILE" | sed "s|.*${BACKEND_DIR}/||")
      docker compose -f "$CLAUDE_PROJECT_DIR/docker-compose.yml" exec -T "${BACKEND_SERVICE}" \
        uv run ruff format "$RELPATH" 2>/dev/null || true
    fi

    # Auto-format frontend .ts/.tsx files with prettier.
    if [ -n "$FILE" ] && echo "$FILE" | grep -q "${FRONTEND_DIR}/.*\.\(ts\|tsx\)$"; then
      ${FRONTEND_NODE_CMD} --prefix "$CLAUDE_PROJECT_DIR/${FRONTEND_DIR}" \
        prettier --write "$FILE" 2>/dev/null || true
    fi
    ;;

  check-bash)
    # Called by PostToolUse on Bash.
    # Stdin: JSON with tool_input.command
    INPUT=$(cat)
    CMD=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

    # Mark dirty + changed if Bash command copies/moves .py files. Invalidate prior review.
    if echo "$CMD" | grep -qE '(cp |mv ).*\.py'; then
      touch "$DIRTY"
      touch "$CHANGED"
      rm -f "$REVIEWED"
    fi

    # Mark fe-dirty + fe-changed if Bash command copies/moves .ts/.tsx files. Invalidate prior review.
    if echo "$CMD" | grep -qE '(cp |mv ).*\.(ts|tsx)'; then
      touch "$FE_DIRTY"
      touch "$FE_CHANGED"
      rm -f "$REVIEWED"
    fi

    # Clear dirty if a backend quality check command was run.
    # Matches: ruff check, ty check, pytest, python -m checks
    # Does NOT match: ruff format alone (formatting ≠ validation)
    if echo "$CMD" | grep -qE '(ruff check|ty check|pytest|python -m checks)'; then
      rm -f "$DIRTY"
    fi

    # Clear fe-dirty if a frontend quality check command was run.
    # Matches: tsc (word boundary), eslint, npm run lint, npm run build
    if echo "$CMD" | grep -qE '(\btsc\b|eslint|npm run lint|npm run build)'; then
      rm -f "$FE_DIRTY"
    fi
    ;;

  stop-gate)
    # Called by Stop hook.
    # No stdin needed — just check the markers.
    BLOCKED=false
    MSG=""

    if [ -f "$DIRTY" ]; then
      BLOCKED=true
      MSG+="Backend code was modified but quality checks were not run.
Run: ${BACKEND_RUN} ruff check --fix . \\
  && ${BACKEND_RUN} ruff format . \\
  && ${BACKEND_UVX} ty check

"
    fi

    if [ -f "$FE_DIRTY" ]; then
      BLOCKED=true
      MSG+="Frontend code was modified but checks were not run.
Run: cd ${FRONTEND_DIR} && npx tsc --noEmit && npm run lint

"
    fi

    if { [ -f "$CHANGED" ] || [ -f "$FE_CHANGED" ]; } && [ ! -f "$REVIEWED" ]; then
      BLOCKED=true
      MSG+="Code was modified but agent reviews have not run.
Run /review-all or /dev-loop to complete the review loop.
"
    fi

    # Test contract verification: if a contract exists, it must have no
    # unchecked CRITICAL/HIGH items. If no contract exists, warn but don't
    # block — the contract may not exist because only harness/doc files were
    # changed, or because /review-all was used instead of /dev-loop.
    # The contract is the HARD gate; its absence is a soft nudge.
    if { [ -f "$CHANGED" ] || [ -f "$FE_CHANGED" ]; } && [ -f "$REVIEWED" ]; then
      if [ ! -f "$CONTRACT" ]; then
        echo "Note: no test contract found. If production code was changed, run /dev-loop (not /review-all) to generate one." >&2
      elif grep -qE '\- \[ \].*\b(CRITICAL|HIGH)\b' "$CONTRACT" 2>/dev/null; then
        UNCOVERED=$(grep -cE '\- \[ \].*\b(CRITICAL|HIGH)\b' "$CONTRACT" 2>/dev/null || true)
        BLOCKED=true
        MSG+="Test contract has $UNCOVERED uncovered CRITICAL/HIGH items.
Write the missing tests and re-run /dev-loop to satisfy the contract.
See: $CONTRACT
"
      fi
    fi

    # Doc contract verification: same pattern as test contract.
    # If a doc contract exists, it must have no unchecked HIGH items.
    # If no doc contract exists, don't block — it may not exist because
    # /review-all was used or only harness files were changed.
    if { [ -f "$CHANGED" ] || [ -f "$FE_CHANGED" ]; } && [ -f "$REVIEWED" ]; then
      if [ -f "$DOC_CONTRACT" ] && grep -qE '\- \[ \].*\bHIGH\b' "$DOC_CONTRACT" 2>/dev/null; then
        DOC_UNCOVERED=$(grep -cE '\- \[ \].*\bHIGH\b' "$DOC_CONTRACT" 2>/dev/null || true)
        BLOCKED=true
        MSG+="Doc contract has $DOC_UNCOVERED uncovered HIGH items.
Update the docs and check them off in Step 5 of /dev-loop.
See: $DOC_CONTRACT
"
      fi
    fi

    if [ "$BLOCKED" = true ]; then
      echo "$MSG" >&2
      exit 2
    fi

    # ── Non-blocking reminders ──────────────────────────────────────────
    # These don't block exit but nudge the agent on things that are hard
    # to mechanize fully. A mechanical reminder > trusting agent memory.

    # Doc freshness reminder.
    if { [ -f "$CHANGED" ] || [ -f "$FE_CHANGED" ]; } && [ ! -f "$DOCS_TOUCHED" ]; then
      echo "Reminder: code was modified but no docs were updated." >&2
      echo "Consider: EP progress, tech-debt tracker, CLAUDE.md, doc index." >&2
    fi

    # Test contract existence reminder.
    if { [ -f "$CHANGED" ] || [ -f "$FE_CHANGED" ]; } && [ -f "$REVIEWED" ] && [ ! -f "$CONTRACT" ]; then
      echo "Reminder: no test contract found. Run /dev-loop (not /review-all) for test coverage planning." >&2
    fi

    # Doc contract existence reminder.
    if { [ -f "$CHANGED" ] || [ -f "$FE_CHANGED" ]; } && [ -f "$REVIEWED" ] && [ ! -f "$DOC_CONTRACT" ]; then
      echo "Reminder: no doc contract found. Run /dev-loop (not /review-all) for doc update planning." >&2
    fi

    # ADR reminder — if new files were added in cross-service directories.
    if [ -f "$CHANGED" ] && [ -f "$REVIEWED" ]; then
      # Check git diff for new files in ports/ or infrastructure/services/
      NEW_CROSS_SERVICE=$(git -C "$CLAUDE_PROJECT_DIR" diff --name-only --diff-filter=A 2>/dev/null | \
        grep -cE '(application/ports/|infrastructure/services/)' || true)
      if [ "${NEW_CROSS_SERVICE:-0}" -gt 0 ]; then
        echo "Reminder: new port or adapter added. Consider whether an ADR is needed (docs/adr/)." >&2
      fi
    fi

    # Self-check reminder — always fires on session exit.
    # Nudges the agent to ask itself: "Am I done, or am I stopping prematurely?"
    echo "" >&2
    echo "Before you stop — ask yourself:" >&2
    echo "  1. Is there remaining work I can do without human input?" >&2
    echo "  2. Did I verify my changes E2E against the running system?" >&2
    echo "  3. Are there background agents still running that I should wait for?" >&2
    echo "If yes to any: keep going. If no: you're done." >&2
    ;;

  *)
    echo "Usage: quality-gate.sh {mark-edit|check-bash|stop-gate}" >&2
    exit 1
    ;;
esac
