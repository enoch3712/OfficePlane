#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./sync_and_run.sh "python -m pytest"
# Syncs the environment and then runs the provided command via uv.

cmd="${1:-}"
if [[ -z "$cmd" ]]; then
  echo "Usage: $0 '<command>'" >&2
  exit 1
fi

uv sync --dev
uv run $cmd
