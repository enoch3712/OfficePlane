#!/usr/bin/env bash
# Session start context primer — gives agents fresh orientation.
# Runs once at session start to display git state, service health,
# enforcement markers, and active execution plans.
#
# Usage: Run manually at the start of a session:
#   ! .claude/hooks/session-start.sh
#
# Why not a hook? Claude Code hooks (PreToolUse/PostToolUse/Stop) fire on
# every matching tool call. There is no one-shot "session start" event.
# Wiring this as a PreToolUse hook would require a stateful guard file to
# prevent it from firing on every tool call, adding complexity for little
# gain. Running it manually is simpler and explicit.
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"

# Load project config
# shellcheck source=../../harness.config.sh
source "$PROJECT_DIR/harness.config.sh"

echo "=== Agent Session Context ==="
echo ""

# 1. Git state
echo "## Git Status"
git -C "$PROJECT_DIR" branch --show-current
git -C "$PROJECT_DIR" log --oneline -5
echo ""

# 2. Service health (quick, non-blocking)
echo "## Service Health"
if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps --format '{{.Name}} {{.Status}}' 2>/dev/null | head -10; then
  :
else
  echo "Docker Compose not running or not available"
fi
echo ""

# 3. Enforcement state
echo "## Enforcement Markers"
for marker in dirty changed reviewed fe-dirty fe-changed docs-touched; do
  FILE="/tmp/.claude-${marker}-${HARNESS_PROJECT_SLUG}"
  if [ -f "$FILE" ]; then
    echo "  $marker: SET ($(date -r "$FILE" '+%H:%M'))"
  else
    echo "  $marker: clear"
  fi
done

# Test contract
CONTRACT="/tmp/.test-contract-${HARNESS_PROJECT_SLUG}.md"
if [ -f "$CONTRACT" ]; then
  TOTAL=$(grep -cE '^\- \[[ x]\]' "$CONTRACT" 2>/dev/null || echo 0)
  CHECKED=$(grep -cE '^\- \[x\]' "$CONTRACT" 2>/dev/null || echo 0)
  UNCHECKED_CRIT=$(grep -cE '^\- \[ \].*CRITICAL' "$CONTRACT" 2>/dev/null || true)
  echo "  contract: $CHECKED/$TOTAL checked ($UNCHECKED_CRIT critical uncovered)"
else
  echo "  contract: none"
fi
echo ""

# 4. Quality scorecard (last entry)
SCORECARD="$PROJECT_DIR/docs/generated/score-history.csv"
if [ -f "$SCORECARD" ]; then
  echo "## Last Quality Score"
  tail -1 "$SCORECARD"
  echo ""
fi

# 5. Active execution plans
echo "## Active Execution Plans"
if ls "$PROJECT_DIR/docs/exec-plans/active/"*.md 1>/dev/null 2>&1; then
  for plan in "$PROJECT_DIR/docs/exec-plans/active/"*.md; do
    echo "  $(basename "$plan" .md)"
  done
else
  echo "  (none)"
fi
echo ""

# 6. Open tech debt
TECH_DEBT="$PROJECT_DIR/docs/exec-plans/tech-debt-tracker.md"
if [ -f "$TECH_DEBT" ]; then
  OPEN_ITEMS=$(grep -cE '^\|.*\bOpen\b' "$TECH_DEBT" 2>/dev/null || echo 0)
  if [ "$OPEN_ITEMS" -gt 0 ]; then
    echo "## Tech Debt: $OPEN_ITEMS open items"
    grep -E '^\|.*\bOpen\b' "$TECH_DEBT" | head -5 || true
    echo ""
  fi
fi

echo "=== End Session Context ==="
