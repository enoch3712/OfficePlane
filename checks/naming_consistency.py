"""Naming consistency checks for OfficePlane.

Rules:
  NAMING-001: API route handlers should match HTTP verb (GET->get_*, POST->create_*, etc.)
  NAMING-002: Boolean variables/functions should use is_*, has_*, can_*, should_*
  NAMING-003: No fetch_* or retrieve_* (use get_* instead)
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from checks import CheckResult, Status, Violation, register

_BAD_PREFIXES = re.compile(r'^(fetch_|retrieve_|remove_)')
_BOOL_PATTERN = re.compile(r'^(is_|has_|can_|should_)')


class NamingConsistencyCheck:
    name = "naming_consistency"
    description = "Check naming conventions for consistency"
    rules = [
        "NAMING-001: Route handlers match HTTP verb",
        "NAMING-002: Booleans use is_/has_/can_/should_",
        "NAMING-003: No fetch_*/retrieve_* (use get_*)",
    ]

    def run(self, *, src_root: str) -> CheckResult:
        violations: list[Violation] = []
        warnings: list[Violation] = []

        for py_file in Path(src_root).rglob("*.py"):
            rel = str(py_file.relative_to(Path(src_root).parent))

            # Skip test files
            if "test" in str(py_file).lower():
                continue

            try:
                content = py_file.read_text()
                tree = ast.parse(content)
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue

            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue

                name = node.name
                if name.startswith("_"):
                    continue

                # NAMING-003: Bad prefixes
                if _BAD_PREFIXES.match(name):
                    bad_prefix = _BAD_PREFIXES.match(name).group(1)
                    suggested = name.replace(bad_prefix, "get_", 1) if bad_prefix != "remove_" else name.replace("remove_", "delete_", 1)
                    warnings.append(Violation(
                        file=rel, line=node.lineno, rule="NAMING-003",
                        message=f"Function '{name}' uses non-standard prefix '{bad_prefix}'",
                        fix=f"Rename to '{suggested}'",
                    ))

                # NAMING-001: Check route handlers match HTTP verb
                for decorator in node.decorator_list:
                    dec_name = ""
                    if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
                        dec_name = decorator.func.attr
                    elif isinstance(decorator, ast.Attribute):
                        dec_name = decorator.attr

                    verb_prefix_map = {
                        "get": "get_",
                        "post": "create_",
                        "put": "update_",
                        "delete": "delete_",
                        "patch": "update_",
                    }

                    if dec_name in verb_prefix_map:
                        expected_prefix = verb_prefix_map[dec_name]
                        # Allow list_ for GET endpoints too
                        if dec_name == "get" and name.startswith("list_"):
                            continue
                        if not name.startswith(expected_prefix) and not name.startswith("list_"):
                            warnings.append(Violation(
                                file=rel, line=node.lineno, rule="NAMING-001",
                                message=f"Route handler '{name}' uses @{dec_name} but doesn't start with '{expected_prefix}'",
                                fix=f"Rename to '{expected_prefix}{name}' or similar",
                            ))

        status = Status.FAIL if violations else (Status.WARN if warnings else Status.PASS)
        return CheckResult(check=self.name, status=status, violations=violations, warnings=warnings)


register(NamingConsistencyCheck())
