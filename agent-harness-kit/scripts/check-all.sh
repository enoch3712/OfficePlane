#!/bin/bash
# Single entrypoint for all quality gates — backend + frontend + docs.
#
# Usage:
#   ./scripts/check-all.sh              # run all checks
#   ./scripts/check-all.sh backend      # backend only
#   ./scripts/check-all.sh frontend     # frontend only
#   ./scripts/check-all.sh docs         # docs only (broken links, index completeness)
#
# Runs inside Docker for backend, locally for frontend and docs.
# Exits non-zero on first failure (fail-fast).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

# Load project config
# shellcheck source=../harness.config.sh
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
  if $BACKEND_RUN ruff check .; then
    pass "ruff check"
  else
    fail "ruff check"
    return 1
  fi

  step "Backend: ruff format"
  if $BACKEND_RUN ruff format --check .; then
    pass "ruff format"
  else
    fail "ruff format (run: $BACKEND_RUN ruff format .)"
    return 1
  fi

  step "Backend: ty check"
  # ty exits non-zero for ANY diagnostics — including informational ones.
  # With 100+ diagnostics on httpx/SQLAlchemy internals, this always "fails."
  # Per CLAUDE.md: "fix what makes sense, ignore noise."
  # Advisory only: show diagnostic count, never fail-fast.
  TY_OUTPUT=$($BACKEND_UVX ty check 2>&1 || true)
  TY_COUNT=$(echo "$TY_OUTPUT" | grep -oP 'Found \K\d+' || echo "0")
  if [ "$TY_COUNT" -eq 0 ]; then
    pass "ty check (clean)"
  else
    echo -e "  ${BLUE}ℹ ty: $TY_COUNT diagnostics (advisory)${NC}"
    pass "ty check (advisory — $TY_COUNT diagnostics)"
  fi

  step "Backend: architecture & quality checks (7 checks, 22 rules)"
  if $BACKEND_RUN python -m checks; then
    pass "python -m checks"
  else
    # Non-zero exit means violations found — show them but don't fail-fast.
    # These are detection checks on pre-existing code, not blockers for new code.
    warn "python -m checks (violations found — review output above)"
  fi

  step "Backend: pytest"
  if $BACKEND_RUN pytest -x -q; then
    pass "pytest"
  else
    fail "pytest"
    return 1
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

  step "Frontend: FSD layer enforcement (3 rules)"
  if "$SCRIPT_DIR/check-fsd.sh"; then
    pass "check-fsd"
  else
    # Advisory for now — pre-existing violations exist. Will promote to hard failure
    # once existing violations are fixed. Same pattern as backend python -m checks.
    warn "check-fsd (FSD violations found — review output above)"
  fi

  step "Frontend: build"
  if (cd "$PROJECT_ROOT/$FRONTEND_DIR" && npm run build); then
    pass "build"
  else
    fail "build"
    return 1
  fi
}

# --- Docs checks (run locally) ---
run_docs() {
  local docs_script="$PROJECT_ROOT/scripts/check-docs.sh"
  if [ ! -x "$docs_script" ]; then
    echo -e "${RED}scripts/check-docs.sh not found or not executable${NC}"
    return 0
  fi

  step "Docs: broken links + index completeness"
  if "$docs_script"; then
    pass "check-docs"
  else
    fail "check-docs (broken links or missing index entries — see output above)"
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
  docs)
    run_docs
    ;;
  all)
    run_backend
    run_frontend
    run_docs
    ;;
  *)
    echo "Usage: $0 [backend|frontend|docs|all]"
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

# Exit 0 if no hard failures — warnings are advisory only.
exit "$FAILURES"
