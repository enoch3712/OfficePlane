"""LAYER-001 through LAYER-005: Hexagonal layer dependency validation.

Uses Python's ast module to parse imports statically — no runtime execution.
Each file's layer is determined by its path under src/.

Dependency rules (inward only):
    domain/         → NOTHING from src/ (pure Python, stdlib only)
    application/    → domain/ only
    infrastructure/ → domain/ + application/ only
    api/            → domain/ + application/ only
    api/dependencies/ → EXCEPTION: also allowed infrastructure/ (composition root)

Run:
    uv run python -m checks --check=layer_deps
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from checks import CheckResult, Status, Violation, register

# The four architectural layers in our hexagonal backend.
LAYERS = ("domain", "application", "infrastructure", "api")

# What each layer is ALLOWED to import from (within src/).
# Empty set = no src/ imports allowed.
ALLOWED_IMPORTS: dict[str, set[str]] = {
    "domain": set(),
    "application": {"domain"},
    "infrastructure": {"domain", "application"},
    "api": {"domain", "application"},
}

# The composition root exception: api/dependencies/, api/v1/dependencies/,
# and api/v1/main.py may also import from infrastructure/ for DI wiring
# and application lifecycle management.
COMPOSITION_ROOT_PATTERNS = (
    "api/dependencies/",
    "api/v1/dependencies/",
    "api/v1/main.py",
)

RULE_MAP = {
    "domain": "LAYER-001: domain/ must not import from any other src/ layer (pure Python only)",
    "application": "LAYER-002: application/ can only import from domain/",
    "infrastructure": "LAYER-003: infrastructure/ can only import from domain/ and application/",
    "api": "LAYER-004: api/ can only import from domain/ and application/",
    "api_composition": "LAYER-005: only api/dependencies/ may import from infrastructure/ (composition root)",
}


def _classify_layer(*, file_path: str, src_root: str) -> str | None:
    """Determine which architectural layer a file belongs to."""
    relative = str(Path(file_path).relative_to(src_root))
    for layer in LAYERS:
        if relative.startswith(f"{layer}/") or relative.startswith(f"{layer}\\"):
            return layer
    return None


def _is_composition_root(*, file_path: str, src_root: str) -> bool:
    """Check if a file is in the DI composition root (api/dependencies/)."""
    relative = str(Path(file_path).relative_to(src_root)).replace("\\", "/")
    return any(relative.startswith(pattern) for pattern in COMPOSITION_ROOT_PATTERNS)


def _extract_src_imports(*, tree: ast.AST) -> list[tuple[str, int]]:
    """Extract all imports that reference src/ layers, returning (target_layer, line_number)."""
    imports: list[tuple[str, int]] = []

    for node in ast.walk(tree):
        module: str | None = None

        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name
                _check_module(module=module, line=node.lineno, imports=imports)
        elif isinstance(node, ast.ImportFrom) and node.module:
            module = node.module
            _check_module(module=module, line=node.lineno, imports=imports)

    return imports


def _check_module(
    *,
    module: str,
    line: int,
    imports: list[tuple[str, int]],
) -> None:
    """If a module path references a src/ layer, record it."""
    # Imports look like: src.domain.models.agent or domain.models.agent
    parts = module.split(".")

    # Handle both "src.domain.xxx" and "domain.xxx" styles.
    target = parts[1] if parts[0] == "src" and len(parts) > 1 else parts[0]

    if target in LAYERS:
        imports.append((target, line))


def _get_allowed_for_file(*, file_path: str, src_root: str, layer: str) -> set[str]:
    """Get the allowed import targets for a specific file, including exceptions."""
    allowed = ALLOWED_IMPORTS[layer].copy()

    # Composition root exception: api/dependencies/ may import infrastructure/.
    if layer == "api" and _is_composition_root(file_path=file_path, src_root=src_root):
        allowed.add("infrastructure")

    return allowed


@dataclass
class LayerDepsCheck:
    """Validates hexagonal layer dependency rules."""

    name: str = "layer_deps"
    description: str = "Hexagonal architecture layer dependency validation"
    rules: list[str] = field(
        default_factory=lambda: [
            "LAYER-001: domain/ must not import from any other src/ layer",
            "LAYER-002: application/ can only import from domain/",
            "LAYER-003: infrastructure/ can only import from domain/ and application/",
            "LAYER-004: api/ can only import from domain/ and application/",
            "LAYER-005: only api/dependencies/ may import from infrastructure/ (composition root)",
        ]
    )

    def run(self, *, src_root: str) -> CheckResult:
        """Scan all Python files under src/ and validate import directions."""
        violations: list[Violation] = []
        warnings: list[Violation] = []
        src_path = Path(src_root)

        for py_file in sorted(src_path.rglob("*.py")):
            file_str = str(py_file)
            layer = _classify_layer(file_path=file_str, src_root=src_root)
            if layer is None:
                continue

            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=file_str)
            except SyntaxError:
                warnings.append(
                    Violation(
                        file=str(py_file.relative_to(src_path)),
                        line=0,
                        rule="LAYER-000: parse error",
                        message=f"Could not parse {py_file.name} — skipping",
                        fix="Fix the syntax error first",
                    )
                )
                continue

            imports = _extract_src_imports(tree=tree)
            allowed = _get_allowed_for_file(file_path=file_str, src_root=src_root, layer=layer)
            is_comp_root = _is_composition_root(file_path=file_str, src_root=src_root)

            for target_layer, line in imports:
                if target_layer == layer:
                    # Same-layer imports are always fine.
                    continue

                if target_layer not in allowed:
                    relative_file = str(py_file.relative_to(src_path))

                    # Pick the right rule ID.
                    if layer == "api" and target_layer == "infrastructure" and not is_comp_root:
                        rule = RULE_MAP["api_composition"]
                        fix = (
                            "Move this import to api/v1/dependencies/ (the composition root) "
                            "or depend on the port in application/ports/ instead"
                        )
                    else:
                        rule = RULE_MAP.get(layer, f"LAYER: {layer}/ cannot import {target_layer}/")
                        fix = _suggest_fix(source_layer=layer, target_layer=target_layer)

                    violations.append(
                        Violation(
                            file=relative_file,
                            line=line,
                            rule=rule,
                            message=f"{layer}/ imports from {target_layer}/",
                            fix=fix,
                        )
                    )

        status = Status.FAIL if violations else (Status.WARN if warnings else Status.PASS)
        return CheckResult(
            check=self.name,
            status=status,
            violations=violations,
            warnings=warnings,
        )


def _suggest_fix(*, source_layer: str, target_layer: str) -> str:
    """Generate a human-readable fix suggestion for a layer violation."""
    suggestions = {
        ("domain", "application"): "Domain must be pure — move the needed type to domain/",
        (
            "domain",
            "infrastructure",
        ): "Domain must be pure — define a port in application/ports/ instead",
        ("domain", "api"): "Domain must be pure — this dependency is inverted",
        (
            "application",
            "infrastructure",
        ): "Depend on a port (Protocol) in application/ports/, not the concrete implementation",
        (
            "application",
            "api",
        ): "Application must not know about the API layer — invert the dependency",
        (
            "api",
            "infrastructure",
        ): "Use dependency injection via api/v1/dependencies/ instead of direct imports",
    }
    return suggestions.get(
        (source_layer, target_layer),
        f"Remove the import from {target_layer}/ — only allowed: {', '.join(ALLOWED_IMPORTS.get(source_layer, set()))}",
    )


# Self-register on import.
register(LayerDepsCheck())
