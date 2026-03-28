#!/usr/bin/env bash
set -euo pipefail

# Usage:
#   ./bootstrap_project.sh myproj
# Creates a new uv project and installs a couple of common dev tools.

project_name="${1:-}"
if [[ -z "$project_name" ]]; then
  echo "Usage: $0 <project_name>" >&2
  exit 1
fi

mkdir -p "$project_name"
cd "$project_name"

uv init
uv add requests
uv add --dev ruff pytest
uv sync --dev

echo "Done. Try:"
echo "  cd $project_name"
echo "  uv run python -c 'import requests; print(requests.__version__)'"
echo "  uv run ruff --version"
