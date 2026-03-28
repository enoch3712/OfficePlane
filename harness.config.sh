#!/usr/bin/env bash
# Agent harness project configuration.
# All harness scripts source this file for project-specific values.
# Run /setup-harness to reconfigure.

# Project slug — used in /tmp marker and contract file names.
HARNESS_PROJECT_SLUG="officeplane"

# Backend
BACKEND_DIR="src"
BACKEND_SERVICE="api"
BACKEND_PACKAGE_MGR="pip"

# Frontend
FRONTEND_DIR="ui"
FRONTEND_NODE_CMD="npx"

# Derived commands
BACKEND_EXEC="docker compose exec -T ${BACKEND_SERVICE}"
BACKEND_RUN="${BACKEND_EXEC} python -m"
BACKEND_PIP="${BACKEND_EXEC} pip"
