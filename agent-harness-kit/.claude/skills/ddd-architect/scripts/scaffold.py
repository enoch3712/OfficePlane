#!/usr/bin/env python3
"""Scaffold a strict DDD/Hexagonal project structure.

Usage:
    python scaffold.py <project_name>

The generated layout enforces these rules:
- Domain is pure Python and has no framework imports.
- Application defines ports (interfaces) and use cases.
- Infrastructure implements ports (SQLAlchemy 2.0 async, Alembic migrations).
- API layer is FastAPI and does orchestration only.

This script intentionally generates a minimal starter structure.
"""

from __future__ import annotations

import sys
from pathlib import Path


def create_text_file(*, path: Path, content: str = "") -> None:
    """Create a file and parent directories.

    Args:
        path: File path to write.
        content: File content.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Created: {path}")


def _usage_exit(*, code: int) -> None:
    print("Usage: python scaffold.py <project_name>")
    raise SystemExit(code)


def main() -> None:
    """Entrypoint."""

    if len(sys.argv) < 2:
        _usage_exit(code=1)

    root = Path(sys.argv[1]).resolve()
    src = root / "src"

    # 1) Structure
    directories = [
        src / "domain" / "models",
        src / "application" / "interfaces",
        src / "application" / "use_cases",
        src / "infrastructure" / "db" / "migrations",
        src / "infrastructure" / "repositories",
        src / "api" / "v1" / "endpoints",
        root / "tests" / "unit",
        root / "tests" / "integration",
    ]

    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)
        create_text_file(path=directory / "__init__.py")

    # 2) Core files
    create_text_file(
        path=src / "domain" / "base.py",
        content=(
            "from __future__ import annotations\n\n"
            "from dataclasses import dataclass\n"
            "from uuid import UUID\n\n\n"
            "@dataclass\n"
            "class Entity:\n"
            "    id: UUID\n"
        ),
    )

    create_text_file(
        path=src / "application" / "interfaces" / "uow.py",
        content=(
            "from __future__ import annotations\n\n"
            "from typing import Protocol\n\n\n"
            "class IUnitOfWork(Protocol):\n"
            '    async def __aenter__(self) -> "IUnitOfWork": ...\n\n'
            "    async def __aexit__(\n"
            "        self,\n"
            "        exc_type: type[BaseException] | None,\n"
            "        exc: BaseException | None,\n"
            "        tb: object | None,\n"
            "    ) -> None: ...\n\n"
            "    async def commit(self) -> None: ...\n\n"
            "    async def rollback(self) -> None: ...\n"
        ),
    )

    create_text_file(
        path=src / "infrastructure" / "db" / "config.py",
        content=(
            "from __future__ import annotations\n\n"
            "from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine\n\n\n"
            'DATABASE_URL = "sqlite+aiosqlite:///./app.db"\n\n'
            "engine = create_async_engine(DATABASE_URL)\n"
            "SessionLocal = async_sessionmaker(engine, expire_on_commit=False)\n"
        ),
    )

    create_text_file(
        path=src / "api" / "main.py",
        content=(
            "from __future__ import annotations\n\n"
            "from fastapi import FastAPI\n\n\n"
            'app = FastAPI(title="DDD App")\n\n\n'
            '@app.get("/")\n'
            "async def health() -> dict[str, str]:\n"
            '    return {"status": "ok"}\n'
        ),
    )

    create_text_file(
        path=root / "pyproject.toml",
        content=(
            "[project]\n"
            f'name = "{root.name}"\n'
            'version = "0.1.0"\n'
            'requires-python = ">=3.13"\n'
            "dependencies = [\n"
            '    "fastapi",\n'
            '    "uvicorn",\n'
            '    "sqlalchemy>=2",\n'
            '    "alembic",\n'
            '    "pydantic-settings",\n'
            '    "aiosqlite",\n'
            "]\n"
        ),
    )

    print(f"\n✅ DDD Project '{root.name}' scaffolded successfully.")
    print("Next steps:")
    print(f"  cd {root.name}")
    print("  uv sync  # If using uv")


if __name__ == "__main__":
    main()
