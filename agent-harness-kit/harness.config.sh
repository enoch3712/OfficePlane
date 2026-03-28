#!/usr/bin/env bash
# Agent harness project configuration.
# All harness scripts source this file for project-specific values.
# Run /setup-harness to have Claude configure these for your project.

# Project slug — used in /tmp marker and contract file names.
# Must be unique per project (use repo name or similar).
HARNESS_PROJECT_SLUG="my-project"

# Backend
BACKEND_DIR="backend"
BACKEND_SERVICE="backend"
BACKEND_PACKAGE_MGR="uv"               # uv | pip | poetry

# Frontend
FRONTEND_DIR="frontend"
FRONTEND_NODE_CMD="npx"                 # npx | pnpx | yarn

# Derived commands (override if your setup differs from Docker Compose + uv)
BACKEND_EXEC="docker compose exec -T ${BACKEND_SERVICE}"
BACKEND_RUN="${BACKEND_EXEC} ${BACKEND_PACKAGE_MGR} run"
BACKEND_UVX="${BACKEND_EXEC} uvx"
