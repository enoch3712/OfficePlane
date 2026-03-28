#!/usr/bin/env python3
"""Scaffold a new FSD slice with standard segments and public API.

Usage:
    python new_slice.py <layer> <slice_name>

Example:
    python new_slice.py entities user
"""

from __future__ import annotations

import sys
from pathlib import Path


_VALID_LAYERS: set[str] = {"pages", "widgets", "features", "entities"}


def create_text_file(*, path: Path, content: str = "") -> None:
    """Create a text file and its parent directories.

    Args:
        path: The file path to write.
        content: The content to write.
    """

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Created: {path}")


def _usage_exit(*, code: int) -> None:
    print("Usage: python new_slice.py <layer> <slice_name>")
    print(f"Layers: {sorted(_VALID_LAYERS)}")
    raise SystemExit(code)


def _to_pascal_case(*, value: str) -> str:
    return "".join(part.capitalize() for part in value.split("-"))


def main() -> None:
    if len(sys.argv) < 3:
        _usage_exit(code=1)

    layer = sys.argv[1]
    slice_name = sys.argv[2]

    if layer not in _VALID_LAYERS:
        print(f"Error: Layer must be one of {sorted(_VALID_LAYERS)}")
        raise SystemExit(1)

    root = Path("src") / layer / slice_name

    # 1) Create segments
    for segment in ("ui", "model", "api", "lib"):
        (root / segment).mkdir(parents=True, exist_ok=True)
        create_text_file(path=root / segment / ".gitkeep")

    # 2) Public API
    index_content = (
        f"// Public API for {slice_name}\n"
        "export * from './ui';\n"
        "export * from './model';\n"
    )
    create_text_file(path=root / "index.ts", content=index_content)

    # 3) Sample files
    component_name = _to_pascal_case(value=slice_name)

    ui_content = (
        f"export const {component_name} = () => {{\n"
        "  return (\n"
        f'    <div className="{layer}-{slice_name}">\n'
        f"      {component_name} Component\n"
        "    </div>\n"
        "  );\n"
        "};\n"
    )

    create_text_file(
        path=root / "ui" / "index.ts",
        content=f"export * from './{component_name}';\n",
    )
    create_text_file(path=root / "ui" / f"{component_name}.tsx", content=ui_content)

    model_content = (
        f"// {slice_name} types and state\n"
        f"export interface {component_name}Schema {{}}\n"
    )
    create_text_file(path=root / "model" / "types.ts", content=model_content)
    create_text_file(
        path=root / "model" / "index.ts", content="export * from './types';\n"
    )

    print(f"\n✅ FSD Slice '{slice_name}' created in 'src/{layer}/{slice_name}'")


if __name__ == "__main__":
    main()
