# uv Cheatsheet

## Install

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uv --version
```

## Project lifecycle

```bash
uv init
uv add <pkg>
uv add --dev <pkg>
uv remove <pkg>
uv sync
uv sync --dev
uv sync --frozen
uv run python -m pytest
```

## Running

```bash
uv run python script.py
uv run python -m pip list
uv run ruff check .
```

## One-off tools

```bash
uvx ruff --version
uvx black --version
```

## Python versions

```bash
uv python list
uv python install 3.12
uv python pin 3.12
uv run python -V
```

## CI tip

Use frozen sync to ensure reproducible builds:

```bash
uv sync --frozen --dev
```
