---
name: uv-package-manager
description: Fast Python package + project manager (uv). Covers installation, initializing projects, dependency management, lockfiles, syncing environments, running commands, and managing Python versions.
metadata:
  tool: uv
  language: shell
---

# uv Package Manager

## When to use this skill

Use this skill when you need to set up or modify a Python project using **uv**:

- Create a new project with `uv init`
- Add/remove dependencies while keeping `pyproject.toml` + lockfile consistent
- Create/sync virtual environments deterministically (`uv sync`)
- Run commands inside the uv-managed environment (`uv run`)
- Manage Python versions/interpreters (`uv python ...`)

## Prerequisites

- A working shell (bash/zsh)
- `uv` installed

### Install uv

Pick one:

```bash
# macOS/Linux (recommended installer)
curl -LsSf https://astral.sh/uv/install.sh | sh

# or via Homebrew
brew install uv

# or via pipx
pipx install uv
```

Verify:

```bash
uv --version
```

## Core mental model (happy path)

- `uv` uses `pyproject.toml` as the source of truth for dependencies.
- `uv.lock` records an exact, reproducible resolution.
- `uv sync` makes your environment match the lockfile.

## 1) Start a project

```bash
mkdir myproj && cd myproj
uv init
```

Common variants:

```bash
uv init --app      # application
uv init --lib      # library
```

## 2) Add / remove dependencies

Add a runtime dependency:

```bash
uv add requests
```

Add a dev dependency:

```bash
uv add --dev ruff
```

Remove:

```bash
uv remove requests
```

What to expect:

- `pyproject.toml` gets updated
- `uv.lock` gets created/updated

## 3) Sync environment

Create/update the venv to match the lockfile:

```bash
uv sync
```

Common options:

```bash
uv sync --dev      # include dev dependencies
uv sync --frozen   # fail if lockfile would change
```

## 4) Run commands (inside env)

```bash
uv run python -V
uv run python -m pytest
uv run ruff check .
```

If you need a one-off tool without permanently adding it:

```bash
uvx ruff --version
```

## 5) Python version management

List/install/select Python versions via uv:

```bash
uv python list
uv python install 3.12
uv python pin 3.12
```

## Common issues & fixes

- Lockfile drift: run `uv sync` (or use `uv sync --frozen` in CI).
- Wrong interpreter: use `uv python pin <version>` then `uv sync`.
- Confusing venv state: remove `.venv/` and re-run `uv sync`.

## References

- Quick cheatsheet: [references/cheatsheet.md](references/cheatsheet.md)
- Example `pyproject.toml`: [references/pyproject.example.toml](references/pyproject.example.toml)
- Scripts:
  - [scripts/bootstrap_project.sh](scripts/bootstrap_project.sh)
  - [scripts/sync_and_run.sh](scripts/sync_and_run.sh)
