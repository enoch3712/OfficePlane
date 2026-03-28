"""PATTERN-001 through PATTERN-004: Pattern divergence detection.

Promoted from entropy-sweep-01 findings into mechanical enforcement.

Rules:
    PATTERN-001  No inline imports inside functions — all imports at module level
    PATTERN-002  No TYPE_CHECKING guards outside infrastructure/db/models/
    PATTERN-003  Registry proxy endpoints must use consistent try/except RegistryClientError (warning)
    PATTERN-004  Endpoint functions should not exceed nesting depth of 4 (warning)

Run:
    uv run python -m checks --check=pattern_divergence
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from checks import CheckResult, Status, Violation, register

# ---------------------------------------------------------------------------
# PATTERN-001: No inline imports inside functions
# ---------------------------------------------------------------------------

_MODELS_DIR = "infrastructure/db/models"

# Directories where conditional inline imports are legitimate:
# - observability: OTel instrumentation packages loaded conditionally
# - main.py: app factory wires dependencies at startup
_PATTERN_001_EXEMPT_PATHS = (
    "infrastructure/observability/",
    "api/v1/main.py",
)


def _is_inside_function(*, node: ast.AST, parents: dict[int, ast.AST]) -> bool:
    """Walk up the parent chain to see if *node* is inside a function body."""
    current_id = id(node)
    while current_id in parents:
        parent = parents[current_id]
        if isinstance(parent, ast.FunctionDef | ast.AsyncFunctionDef):
            return True
        current_id = id(parent)
    return False


def _is_inside_type_checking_guard(
    *,
    node: ast.AST,
    parents: dict[int, ast.AST],
) -> bool:
    """Return True if *node* lives inside an ``if TYPE_CHECKING:`` block."""
    current_id = id(node)
    while current_id in parents:
        parent = parents[current_id]
        if isinstance(parent, ast.If):
            test = parent.test
            # Plain ``TYPE_CHECKING``
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                return True
            # ``typing.TYPE_CHECKING``
            if isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING":
                return True
        current_id = id(parent)
    return False


def _build_parent_map(*, tree: ast.AST) -> dict[int, ast.AST]:
    """Build a child-id → parent mapping for the entire AST."""
    parents: dict[int, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[id(child)] = parent
    return parents


def _line_has_noqa(*, source_lines: list[str], lineno: int, rule: str) -> bool:
    """Return True if the source line has a ``# noqa: <rule>`` comment."""
    if 1 <= lineno <= len(source_lines):
        line = source_lines[lineno - 1]
        if f"# noqa: {rule}" in line:
            return True
    return False


def _check_inline_imports(
    *,
    tree: ast.AST,
    source_lines: list[str],
    relative_file: str,
) -> list[Violation]:
    """PATTERN-001: Find import statements inside function bodies."""
    # Exempt paths where conditional imports are legitimate.
    normalized = relative_file.replace("\\", "/")
    for exempt in _PATTERN_001_EXEMPT_PATHS:
        if normalized.startswith(exempt) or normalized == exempt:
            return []

    violations: list[Violation] = []
    parents = _build_parent_map(tree=tree)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Import | ast.ImportFrom):
            continue

        if not _is_inside_function(node=node, parents=parents):
            continue

        # Exempt imports inside TYPE_CHECKING guards (though discouraged).
        if _is_inside_type_checking_guard(node=node, parents=parents):
            continue

        if _line_has_noqa(
            source_lines=source_lines,
            lineno=node.lineno,
            rule="PATTERN-001",
        ):
            continue

        # Build a human-readable module name for the message.
        if isinstance(node, ast.ImportFrom):
            module_name = node.module or "<relative>"
        else:
            module_name = ", ".join(alias.name for alias in node.names)

        violations.append(
            Violation(
                file=relative_file,
                line=node.lineno,
                rule="PATTERN-001: No inline imports inside functions",
                message=f"Import '{module_name}' found inside a function body",
                fix="Move this import to the top of the file, at module level",
            ),
        )

    return violations


# ---------------------------------------------------------------------------
# PATTERN-002: No TYPE_CHECKING guards in non-model files
# ---------------------------------------------------------------------------


def _check_type_checking_guards(
    *,
    tree: ast.AST,
    source_lines: list[str],
    relative_file: str,
) -> list[Violation]:
    """PATTERN-002: Find ``if TYPE_CHECKING:`` blocks outside models/observability dirs."""
    # Exempt files under infrastructure/db/models/ (SQLAlchemy forward refs)
    # and infrastructure/observability/ (conditional OTel type imports).
    normalized = relative_file.replace("\\", "/")
    if normalized.startswith(_MODELS_DIR) or normalized.startswith("infrastructure/observability/"):
        return []

    violations: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue

        test = node.test
        is_tc_guard = False

        if (
            isinstance(test, ast.Name)
            and test.id == "TYPE_CHECKING"
            or isinstance(test, ast.Attribute)
            and test.attr == "TYPE_CHECKING"
        ):
            is_tc_guard = True

        if not is_tc_guard:
            continue

        if _line_has_noqa(
            source_lines=source_lines,
            lineno=node.lineno,
            rule="PATTERN-002",
        ):
            continue

        violations.append(
            Violation(
                file=relative_file,
                line=node.lineno,
                rule="PATTERN-002: No TYPE_CHECKING guards in non-model files",
                message="if TYPE_CHECKING: block found — import types directly at the top",
                fix=(
                    "Remove the TYPE_CHECKING guard and import the type directly. "
                    "Only infrastructure/db/models/ is exempt (SQLAlchemy forward refs)"
                ),
            ),
        )

    return violations


# ---------------------------------------------------------------------------
# PATTERN-003: Registry proxy endpoints must use consistent error handling
# ---------------------------------------------------------------------------

_REGISTRY_FILE = "api/v1/endpoints/registry.py"


def _check_registry_error_handling(
    *,
    tree: ast.AST,
    source_lines: list[str],
    relative_file: str,
) -> list[Violation]:
    """PATTERN-003: Verify all registry endpoint functions that call the client use try/except."""
    normalized = relative_file.replace("\\", "/")
    if normalized != _REGISTRY_FILE:
        return []

    warnings: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue

        # Does this function call a method on any variable named *registry*?
        calls_registry = False
        for child in ast.walk(node):
            if (
                isinstance(child, ast.Attribute)
                and isinstance(child.value, ast.Name)
                and child.value.id in ("registry", "registry_client")
            ):
                calls_registry = True
                break

        if not calls_registry:
            continue

        # Does this function have a try/except that catches RegistryClientError?
        has_try_except = False
        for child in ast.walk(node):
            if not isinstance(child, ast.ExceptHandler):
                continue
            if child.type is None:
                # Bare except — not our pattern.
                continue
            # Check if the exception type is RegistryClientError.
            exc_type = child.type
            if isinstance(exc_type, ast.Name) and exc_type.id == "RegistryClientError":
                has_try_except = True
                break
            if isinstance(exc_type, ast.Attribute) and exc_type.attr == "RegistryClientError":
                has_try_except = True
                break

        if not has_try_except:
            if _line_has_noqa(
                source_lines=source_lines,
                lineno=node.lineno,
                rule="PATTERN-003",
            ):
                continue

            warnings.append(
                Violation(
                    file=relative_file,
                    line=node.lineno,
                    rule="PATTERN-003: Registry endpoints must use consistent error handling (warning)",
                    message=(
                        f"Function '{node.name}' calls registry client but lacks "
                        "try/except RegistryClientError pattern"
                    ),
                    fix=(
                        "Wrap the registry call in try/except RegistryClientError "
                        "and raise HTTPException(502) — see other endpoints in this file"
                    ),
                ),
            )

    return warnings


# ---------------------------------------------------------------------------
# PATTERN-004: Endpoint functions should not exceed complexity threshold
# ---------------------------------------------------------------------------

_ENDPOINTS_DIR = "api/v1/endpoints"
_MAX_NESTING_DEPTH = 4

# AST node types that introduce a new nesting level.
_NESTING_NODES = (
    ast.If,
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.With,
    ast.AsyncWith,
    ast.Try,
    ast.ExceptHandler,
)


def _max_nesting_depth(*, node: ast.AST, depth: int = 0) -> int:
    """Recursively compute the maximum nesting depth of control-flow nodes."""
    max_depth = depth

    for child in ast.iter_child_nodes(node):
        if isinstance(child, _NESTING_NODES):
            child_depth = _max_nesting_depth(node=child, depth=depth + 1)
        else:
            child_depth = _max_nesting_depth(node=child, depth=depth)
        max_depth = max(max_depth, child_depth)

    return max_depth


def _check_endpoint_nesting(
    *,
    tree: ast.AST,
    source_lines: list[str],
    relative_file: str,
) -> list[Violation]:
    """PATTERN-004: Flag endpoint functions with nesting > 4 levels."""
    normalized = relative_file.replace("\\", "/")
    if not normalized.startswith(_ENDPOINTS_DIR):
        return []

    warnings: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue

        depth = _max_nesting_depth(node=node)
        if depth <= _MAX_NESTING_DEPTH:
            continue

        if _line_has_noqa(
            source_lines=source_lines,
            lineno=node.lineno,
            rule="PATTERN-004",
        ):
            continue

        warnings.append(
            Violation(
                file=relative_file,
                line=node.lineno,
                rule="PATTERN-004: Endpoint nesting depth exceeds threshold (warning)",
                message=(
                    f"Function '{node.name}' has nesting depth {depth} "
                    f"(max {_MAX_NESTING_DEPTH}) — consider extracting helper functions"
                ),
                fix=(
                    "Extract deeply nested logic into private helper functions "
                    "or service methods to reduce cognitive complexity"
                ),
            ),
        )

    return warnings


# ---------------------------------------------------------------------------
# Check class + registration
# ---------------------------------------------------------------------------


@dataclass
class PatternDivergenceCheck:
    """Detects pattern divergence promoted from entropy-sweep-01 into mechanical enforcement."""

    name: str = "pattern_divergence"
    description: str = (
        "Pattern divergence detection (inline imports, TYPE_CHECKING, endpoint consistency)"
    )
    rules: list[str] = field(
        default_factory=lambda: [
            "PATTERN-001: No inline imports inside functions",
            "PATTERN-002: No TYPE_CHECKING guards in non-model files",
            "PATTERN-003: Registry endpoints must use consistent error handling (warning)",
            "PATTERN-004: Endpoint nesting depth exceeds threshold (warning)",
        ],
    )

    def run(self, *, src_root: str) -> CheckResult:
        """Scan Python files under src/ for pattern divergence."""
        violations: list[Violation] = []
        warnings: list[Violation] = []
        src_path = Path(src_root)

        for py_file in sorted(src_path.rglob("*.py")):
            relative_file = str(py_file.relative_to(src_path))

            # Skip test files.
            if Path(relative_file).name.startswith("test_"):
                continue

            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                warnings.append(
                    Violation(
                        file=relative_file,
                        line=0,
                        rule="PATTERN-000: parse error",
                        message=f"Could not parse {py_file.name} — skipping",
                        fix="Fix the syntax error first",
                    ),
                )
                continue

            source_lines = source.splitlines()

            # PATTERN-001: inline imports (violation)
            violations.extend(
                _check_inline_imports(
                    tree=tree,
                    source_lines=source_lines,
                    relative_file=relative_file,
                ),
            )

            # PATTERN-002: TYPE_CHECKING guards (violation)
            violations.extend(
                _check_type_checking_guards(
                    tree=tree,
                    source_lines=source_lines,
                    relative_file=relative_file,
                ),
            )

            # PATTERN-003: registry error handling (warning)
            warnings.extend(
                _check_registry_error_handling(
                    tree=tree,
                    source_lines=source_lines,
                    relative_file=relative_file,
                ),
            )

            # PATTERN-004: endpoint nesting depth (warning)
            warnings.extend(
                _check_endpoint_nesting(
                    tree=tree,
                    source_lines=source_lines,
                    relative_file=relative_file,
                ),
            )

        status = Status.FAIL if violations else (Status.WARN if warnings else Status.PASS)
        return CheckResult(
            check=self.name,
            status=status,
            violations=violations,
            warnings=warnings,
        )


# Self-register on import.
register(PatternDivergenceCheck())
