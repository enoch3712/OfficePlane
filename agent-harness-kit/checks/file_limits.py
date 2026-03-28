"""SIZE-001 through SIZE-003: File size and function length enforcement.

Checks:
    SIZE-001  Python files warn at 300 effective lines, error at 500
    SIZE-002  Functions/methods warn at 50 lines, error at 80
    SIZE-003  Classes with >10 methods are a warning (decomposition candidate)

Effective lines = non-blank, non-comment lines.

Excludes: __init__.py, conftest.py, alembic/, migrations/, test_* prefixed files.

Run:
    uv run python -m checks --check=file_limits
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from checks import CheckResult, Status, Violation, register

# SIZE-001 thresholds (effective lines per file).
FILE_WARN_LINES = 300
FILE_ERROR_LINES = 500

# SIZE-002 thresholds (lines per function/method).
FUNC_WARN_LINES = 50
FUNC_ERROR_LINES = 80

# SIZE-003 threshold (methods per class).
CLASS_METHOD_WARN = 10

# Files and directories excluded from scanning.
EXCLUDED_FILENAMES = {"__init__.py", "conftest.py"}
EXCLUDED_DIR_PARTS = {"alembic", "migrations"}


def _should_exclude(*, file_path: Path) -> bool:
    """Determine whether a file should be skipped based on exclusion rules."""
    if file_path.name in EXCLUDED_FILENAMES:
        return True
    if file_path.name.startswith("test_"):
        return True
    return any(part in EXCLUDED_DIR_PARTS for part in file_path.parts)


def _count_effective_lines(*, source: str) -> int:
    """Count non-blank, non-comment-only lines in source code."""
    count = 0
    for line in source.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        count += 1
    return count


def _check_file_size(
    *,
    source: str,
    relative_file: str,
) -> tuple[list[Violation], list[Violation]]:
    """SIZE-001: Warn at 300 effective lines, error at 500."""
    violations: list[Violation] = []
    warnings: list[Violation] = []
    effective = _count_effective_lines(source=source)

    if effective >= FILE_ERROR_LINES:
        violations.append(
            Violation(
                file=relative_file,
                line=1,
                rule="SIZE-001: File exceeds 500 effective lines",
                message=f"File has {effective} effective lines (limit: {FILE_ERROR_LINES})",
                fix="Split into smaller modules with focused responsibilities",
            ),
        )
    elif effective >= FILE_WARN_LINES:
        warnings.append(
            Violation(
                file=relative_file,
                line=1,
                rule="SIZE-001: File approaching 500 effective lines",
                message=f"File has {effective} effective lines (warn: {FILE_WARN_LINES})",
                fix="Consider splitting into smaller modules before it grows further",
            ),
        )

    return violations, warnings


def _check_function_lengths(
    *,
    tree: ast.AST,
    relative_file: str,
) -> tuple[list[Violation], list[Violation]]:
    """SIZE-002: Warn at 50 lines per function, error at 80."""
    violations: list[Violation] = []
    warnings: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue

        if node.end_lineno is None:
            continue

        length = node.end_lineno - node.lineno + 1

        if length >= FUNC_ERROR_LINES:
            violations.append(
                Violation(
                    file=relative_file,
                    line=node.lineno,
                    rule="SIZE-002: Function exceeds 80 lines",
                    message=f"Function '{node.name}' is {length} lines (limit: {FUNC_ERROR_LINES})",
                    fix="Extract helper functions or simplify control flow",
                ),
            )
        elif length >= FUNC_WARN_LINES:
            warnings.append(
                Violation(
                    file=relative_file,
                    line=node.lineno,
                    rule="SIZE-002: Function approaching 80 lines",
                    message=f"Function '{node.name}' is {length} lines (warn: {FUNC_WARN_LINES})",
                    fix="Consider extracting helper functions before it grows further",
                ),
            )

    return violations, warnings


def _check_class_method_count(
    *,
    tree: ast.AST,
    relative_file: str,
) -> list[Violation]:
    """SIZE-003: Classes with >10 methods are candidates for decomposition."""
    warnings: list[Violation] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        method_count = sum(
            1 for child in node.body if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
        )

        if method_count > CLASS_METHOD_WARN:
            warnings.append(
                Violation(
                    file=relative_file,
                    line=node.lineno,
                    rule="SIZE-003: Class has too many methods",
                    message=f"Class '{node.name}' has {method_count} methods (warn: {CLASS_METHOD_WARN})",
                    fix="Consider decomposing into smaller, focused classes",
                ),
            )

    return warnings


@dataclass
class FileLimitsCheck:
    """Enforces file size and function length limits."""

    name: str = "file_limits"
    description: str = "File size and function/class length enforcement"
    rules: list[str] = field(
        default_factory=lambda: [
            "SIZE-001: Python files warn at 300 effective lines, error at 500",
            "SIZE-002: Functions/methods warn at 50 lines, error at 80",
            "SIZE-003: Classes with >10 methods are a warning",
        ],
    )

    def run(self, *, src_root: str) -> CheckResult:
        """Scan all Python files under src/ and enforce size limits."""
        violations: list[Violation] = []
        warnings: list[Violation] = []
        src_path = Path(src_root)

        for py_file in sorted(src_path.rglob("*.py")):
            if _should_exclude(file_path=py_file):
                continue

            relative_file = str(py_file.relative_to(src_path))

            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                warnings.append(
                    Violation(
                        file=relative_file,
                        line=0,
                        rule="SIZE-000: parse error",
                        message=f"Could not parse {py_file.name} — skipping",
                        fix="Fix the syntax error first",
                    ),
                )
                continue

            # SIZE-001: File effective line count.
            file_violations, file_warnings = _check_file_size(
                source=source,
                relative_file=relative_file,
            )
            violations.extend(file_violations)
            warnings.extend(file_warnings)

            # SIZE-002: Function/method length.
            func_violations, func_warnings = _check_function_lengths(
                tree=tree,
                relative_file=relative_file,
            )
            violations.extend(func_violations)
            warnings.extend(func_warnings)

            # SIZE-003: Class method count.
            warnings.extend(
                _check_class_method_count(tree=tree, relative_file=relative_file),
            )

        status = Status.FAIL if violations else (Status.WARN if warnings else Status.PASS)
        return CheckResult(
            check=self.name,
            status=status,
            violations=violations,
            warnings=warnings,
        )


# Self-register on import.
register(FileLimitsCheck())
