---
name: setup-harness
description: Configure the agent harness for a new project. Detects project structure, asks for confirmation, writes harness.config.sh, and replaces all placeholders.
argument-hint: [optional: skip detection and use these values]
---

Configure the agent harness for this project. Run once after dropping the harness kit into a new repo.

## What This Does

1. Detects or asks for project-specific values
2. Writes `harness.config.sh` with those values
3. Replaces `{{FRONTEND_DIR}}` in `.claude/settings.json`
4. Runs `./scripts/setup-hooks.sh` to install the pre-commit hook
5. Prints a summary and next steps

## Step 1: Detect Project Structure

Inspect the project root to determine:

```bash
# Look for backend (Python)
ls -d */ | grep -E '(backend|api|server|app)' || find . -maxdepth 2 -name "pyproject.toml" -o -name "requirements.txt" | head -5

# Look for frontend (TypeScript/React)
find . -maxdepth 2 -name "package.json" | xargs grep -l '"react"' 2>/dev/null | head -5

# Look for Docker Compose
ls docker-compose*.yml 2>/dev/null || echo "no docker-compose found"

# Check package managers
find . -maxdepth 3 -name "uv.lock" -o -name "poetry.lock" -o -name "Pipfile.lock" | head -3
find . -maxdepth 3 -name "pnpm-lock.yaml" -o -name "yarn.lock" | head -3
```

## Step 2: Ask the User to Confirm

Present findings and ask for confirmation of these 6 values:

```
Detected project structure — please confirm or correct:

1. Project slug (used in /tmp marker names, e.g. "my-app"):
   Suggested: [repo name or directory name]

2. Backend directory name (relative to project root):
   Detected: [detected dir or "not found"]

3. Docker Compose backend service name:
   Detected: [service name from docker-compose.yml or "backend"]

4. Backend package manager:
   Detected: [uv | pip | poetry]

5. Frontend directory name (relative to project root):
   Detected: [detected dir or "not found"]

6. Frontend node command:
   Detected: [npx | pnpx | yarn]
```

If no frontend exists (backend-only project), set `FRONTEND_DIR=""` and skip frontend checks.
If no Docker Compose, set `BACKEND_EXEC="<package_mgr> run"` directly.

## Step 3: Write harness.config.sh

Write the confirmed values to `harness.config.sh` at the project root:

```bash
#!/usr/bin/env bash
# Agent harness project configuration.
# All harness scripts source this file for project-specific values.
# Edit manually or re-run /setup-harness to reconfigure.

HARNESS_PROJECT_SLUG="<slug>"
BACKEND_DIR="<backend_dir>"
BACKEND_SERVICE="<service_name>"
BACKEND_PACKAGE_MGR="<uv|pip|poetry>"
FRONTEND_DIR="<frontend_dir>"
FRONTEND_NODE_CMD="<npx|pnpx|yarn>"

# Derived commands (override if your setup differs from Docker Compose + uv)
BACKEND_EXEC="docker compose exec -T ${BACKEND_SERVICE}"
BACKEND_RUN="${BACKEND_EXEC} ${BACKEND_PACKAGE_MGR} run"
BACKEND_UVX="${BACKEND_EXEC} uvx"
```

For non-Docker setups, set `BACKEND_EXEC` and `BACKEND_RUN` directly (e.g., `BACKEND_RUN="uv run"`).

## Step 4: Replace Placeholders

Replace `{{FRONTEND_DIR}}` in `.claude/settings.json` with the actual frontend directory name:

```bash
sed -i 's|{{FRONTEND_DIR}}|<frontend_dir>|g' .claude/settings.json
```

If backend-only (no frontend), remove the `cd {{FRONTEND_DIR}} *` permission line entirely.

## Step 5: Write CLAUDE.md from Template

If `CLAUDE.template.md` exists and `CLAUDE.md` does NOT already exist:

```bash
cp CLAUDE.template.md CLAUDE.md
# Replace placeholders in CLAUDE.md
sed -i 's|{{HARNESS_PROJECT_SLUG}}|<slug>|g' CLAUDE.md
sed -i 's|{{BACKEND_DIR}}|<backend_dir>|g' CLAUDE.md
sed -i 's|{{FRONTEND_DIR}}|<frontend_dir>|g' CLAUDE.md
sed -i 's|{{BACKEND_STACK}}|Python + <package_mgr> + FastAPI|g' CLAUDE.md
sed -i 's|{{FRONTEND_STACK}}|TypeScript + React + FSD|g' CLAUDE.md
```

If `CLAUDE.md` already exists, skip this step and remind the user to update it manually.

## Step 6: Install Git Hooks

```bash
./scripts/setup-hooks.sh
```

## Step 7: Report

Print a summary:

```
✓ harness.config.sh written
✓ .claude/settings.json updated ({{FRONTEND_DIR}} → <frontend_dir>)
✓ CLAUDE.md generated from template
✓ Git pre-commit hook installed

Next steps:
1. Review harness.config.sh and adjust BACKEND_EXEC/BACKEND_RUN if needed
2. Update CLAUDE.md with your project's specific conventions and docs
3. Review checks/ — remove domain_terms.py or replace with your domain vocabulary
4. Run /validate to confirm the pipeline works end-to-end
5. Read docs/design/enforcement-architecture.md to understand the 3-layer model
```
