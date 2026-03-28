"""File size limit checks for OfficePlane.

Rules:
  SIZE-001: Python files should not exceed 300 lines
  SIZE-002: Functions should not exceed 50 lines
  SIZE-003: Files with >10 route handlers should be split
"""

from __future__ import annotations

import ast
from pathlib import Path

from checks import CheckResult, Status, Violation, register

MAX_FILE_LINES = 300
MAX_FUNCTION_LINES = 50
MAX_ROUTE_HANDLERS = 10


class FileLimitCheck:
    name = "file_limits"
    description = "Check file and function size limits"
    rules = [
        f"SIZE-001: Python files <= {MAX_FILE_LINES} lines",
        f"SIZE-002: Functions <= {MAX_FUNCTION_LINES} lines",
        f"SIZE-003: Files with <= {MAX_ROUTE_HANDLERS} route handlers",
    ]

    def run(self, *, src_root: str) -> CheckResult:
        violations: list[Violation] = []
        warnings: list[Violation] = []

        for py_file in Path(src_root).rglob("*.py"):
            rel = str(py_file.relative_to(Path(src_root).parent))

            # Skip __init__.py and test files
            if py_file.name == "__init__.py" or "test" in str(py_file).lower():
                continue

            try:
                content = py_file.read_text()
                lines = content.splitlines()
            except (OSError, UnicodeDecodeError):
                continue

            # SIZE-001: File length
            if len(lines) > MAX_FILE_LINES:
                warnings.append(Violation(
                    file=rel, line=1, rule="SIZE-001",
                    message=f"File has {len(lines)} lines (limit: {MAX_FILE_LINES})",
                    fix="Split into smaller, focused modules",
                ))

            # Parse AST for function checks
            try:
                tree = ast.parse(content)
            except SyntaxError:
                continue

            route_count = 0
            for node in ast.walk(tree):
                # SIZE-002: Function length
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if hasattr(node, "end_lineno") and node.end_lineno:
                        func_lines = node.end_lineno - node.lineno + 1
                        if func_lines > MAX_FUNCTION_LINES:
                            warnings.append(Violation(
                                file=rel, line=node.lineno, rule="SIZE-002",
                                message=f"Function '{node.name}' has {func_lines} lines (limit: {MAX_FUNCTION_LINES})",
                                fix="Extract helper functions or break into smaller steps",
                            ))

                # SIZE-003: Count route decorators
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for decorator in node.decorator_list:
                        dec_str = ast.dump(decorator)
                        if any(verb in dec_str for verb in ["get", "post", "put", "delete", "patch", "router"]):
                            route_count += 1

            if route_count > MAX_ROUTE_HANDLERS:
                warnings.append(Violation(
                    file=rel, line=1, rule="SIZE-003",
                    message=f"File has {route_count} route handlers (limit: {MAX_ROUTE_HANDLERS})",
                    fix="Split routes into separate files by resource",
                ))

        status = Status.FAIL if violations else (Status.WARN if warnings else Status.PASS)
        return CheckResult(check=self.name, status=status, violations=violations, warnings=warnings)


register(FileLimitCheck())
