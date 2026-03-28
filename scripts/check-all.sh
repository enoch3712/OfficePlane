#!/bin/bash
# Single entrypoint for all quality gates — backend + frontend.
#
# Usage:
#   ./scripts/check-all.sh              # run all checks
#   ./scripts/check-all.sh backend      # backend only
#   ./scripts/check-all.sh frontend     # frontend only

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Load project config
source "$PROJECT_ROOT/harness.config.sh"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

SCOPE="${1:-all}"
FAILURES=0
WARNINGS=0

step() {
  echo -e "\n${BLUE}=== $1 ===${NC}"
}

pass() {
  echo -e "${GREEN}  ✓ $1${NC}"
}

fail() {
  echo -e "${RED}  ✗ $1${NC}"
  FAILURES=$((FAILURES + 1))
}

warn() {
  echo -e "  ${BLUE}⚠ $1${NC}"
  WARNINGS=$((WARNINGS + 1))
}

# --- Backend checks (run in Docker) ---
run_backend() {
  step "Backend: ruff check"
  if $BACKEND_EXEC ruff check src/; then
    pass "ruff check"
  else
    fail "ruff check"
    return 1
  fi

  step "Backend: ruff format"
  if $BACKEND_EXEC ruff format --check src/; then
    pass "ruff format"
  else
    fail "ruff format (run: $BACKEND_EXEC ruff format src/)"
    return 1
  fi

  step "Backend: pytest"
  if $BACKEND_EXEC python -m pytest tests/ -x -q; then
    pass "pytest"
  else
    fail "pytest"
    return 1
  fi

  # Optional: python -m checks (if checks/ module exists)
  if [ -d "$PROJECT_ROOT/checks" ] && [ -f "$PROJECT_ROOT/checks/__main__.py" ]; then
    step "Backend: architecture & quality checks"
    if $BACKEND_EXEC python -m checks; then
      pass "python -m checks"
    else
      warn "python -m checks (violations found — review output above)"
    fi
  fi
}

# --- Frontend checks (run locally) ---
run_frontend() {
  if [ ! -d "$PROJECT_ROOT/$FRONTEND_DIR" ]; then
    echo -e "${RED}${FRONTEND_DIR}/ not found — skipping frontend checks${NC}"
    return 0
  fi

  step "Frontend: TypeScript"
  if (cd "$PROJECT_ROOT/$FRONTEND_DIR" && npx tsc --noEmit); then
    pass "tsc --noEmit"
  else
    fail "tsc --noEmit"
    return 1
  fi

  step "Frontend: ESLint"
  if (cd "$PROJECT_ROOT/$FRONTEND_DIR" && npm run lint); then
    pass "eslint"
  else
    fail "eslint"
    return 1
  fi

  step "Frontend: build"
  if (cd "$PROJECT_ROOT/$FRONTEND_DIR" && npm run build); then
    pass "build"
  else
    fail "build"
    return 1
  fi
}

# --- Main ---
case "$SCOPE" in
  backend)
    run_backend
    ;;
  frontend)
    run_frontend
    ;;
  all)
    run_backend
    run_frontend
    ;;
  *)
    echo "Usage: $0 [backend|frontend|all]"
    exit 1
    ;;
esac

# --- Summary ---
echo ""
if [ "$FAILURES" -eq 0 ] && [ "$WARNINGS" -eq 0 ]; then
  echo -e "${GREEN}=== ALL CHECKS PASSED ===${NC}"
elif [ "$FAILURES" -eq 0 ]; then
  echo -e "${GREEN}=== ALL CHECKS PASSED ===${NC} (${BLUE}$WARNINGS advisory warning(s)${NC})"
else
  echo -e "${RED}=== $FAILURES CHECK(S) FAILED ===${NC}"
fi

exit "$FAILURES"
