#!/usr/bin/env bash
# Configure git to use the version-controlled .githooks/ directory.
#
# Run once after cloning the repo:
#   ./scripts/setup-hooks.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_ROOT"

git config core.hooksPath .githooks

echo "Git hooks configured: core.hooksPath = .githooks"
echo "Pre-commit hook will run quality checks on staged files."
echo "Bypass with: git commit --no-verify"
