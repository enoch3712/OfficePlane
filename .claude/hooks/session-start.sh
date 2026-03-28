#!/usr/bin/env bash
# Session start context primer — gives agents fresh orientation.
# Run manually at session start: ! .claude/hooks/session-start.sh
set -euo pipefail

PROJECT_DIR="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
source "$PROJECT_DIR/harness.config.sh"

echo "=== Agent Session Context ==="
echo ""

echo "## Git Status"
git -C "$PROJECT_DIR" branch --show-current
git -C "$PROJECT_DIR" log --oneline -5
echo ""

echo "## Service Health"
if docker compose -f "$PROJECT_DIR/docker-compose.yml" ps --format '{{.Name}} {{.Status}}' 2>/dev/null | head -10; then
  :
else
  echo "Docker Compose not running or not available"
fi
echo ""

echo "## Enforcement Markers"
for marker in dirty changed reviewed fe-dirty fe-changed docs-touched; do
  FILE="/tmp/.claude-${marker}-${HARNESS_PROJECT_SLUG}"
  if [ -f "$FILE" ]; then
    echo "  $marker: SET ($(date -r "$FILE" '+%H:%M'))"
  else
    echo "  $marker: clear"
  fi
done

CONTRACT="/tmp/.test-contract-${HARNESS_PROJECT_SLUG}.md"
if [ -f "$CONTRACT" ]; then
  TOTAL=$(grep -cE '^\- \[[ x]\]' "$CONTRACT" 2>/dev/null || echo 0)
  CHECKED=$(grep -cE '^\- \[x\]' "$CONTRACT" 2>/dev/null || echo 0)
  echo "  contract: $CHECKED/$TOTAL checked"
else
  echo "  contract: none"
fi
echo ""

echo "=== End Session Context ==="
