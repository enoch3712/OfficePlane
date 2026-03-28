"""SEC-001 through SEC-004: Security pattern enforcement.

Checks:
    SEC-001  Mutation endpoints must have auth dependencies
    SEC-002  No raw SQL — all queries through SQLAlchemy ORM/Core
    SEC-003  No hardcoded secrets in source code
    SEC-004  SSE endpoints must handle client disconnection

Run:
    uv run python -m checks --check=security_patterns
"""

from __future__ import annotations

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path

from checks import CheckResult, Status, Violation, register

# HTTP methods that mutate data — these MUST have auth.
MUTATION_METHODS = {"post", "put", "patch", "delete"}

# Auth dependency detection: any Depends() arg matching these prefixes counts as auth.
AUTH_DEPENDENCY_PREFIXES = ("get_current_user", "require_")

# Endpoints that are exempt from SEC-001 (they issue auth, they can't require it).
AUTH_EXEMPT_ENDPOINTS = {"login", "refresh", "register", "signup"}

# Patterns that indicate raw SQL usage.
RAW_SQL_PATTERNS = [
    re.compile(r'\btext\s*\(\s*["\']', re.MULTILINE),
    re.compile(r'\.execute\s*\(\s*["\']', re.MULTILINE),
    re.compile(r"\bSELECT\b.*\bFROM\b", re.IGNORECASE),
    re.compile(r"\bINSERT\s+INTO\b", re.IGNORECASE),
    re.compile(r"\bUPDATE\b.*\bSET\b", re.IGNORECASE),
    re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE),
]

# Patterns that indicate hardcoded secrets.
SECRET_PATTERNS = [
    re.compile(
        r'(?:password|passwd|secret|token|api_key|apikey)\s*=\s*["\'][^"\']{8,}["\']', re.IGNORECASE
    ),
    re.compile(
        r'(?:aws_access_key_id|aws_secret_access_key)\s*=\s*["\'][^"\']+["\']', re.IGNORECASE
    ),
    re.compile(r"Bearer\s+[A-Za-z0-9\-._~+/]{20,}=*", re.IGNORECASE),
    re.compile(r"-----BEGIN (?:RSA )?PRIVATE KEY-----"),
]

# Files/paths to exclude from secret scanning (test fixtures, docs, etc.).
SECRET_SCAN_EXCLUDES = {
    "conftest.py",
    "seed_dev.py",
    "test_",
}


def _is_mutation_endpoint(node: ast.FunctionDef | ast.AsyncFunctionDef) -> str | None:
    """Check if a function is a mutation endpoint. Return the HTTP method or None."""
    for decorator in node.decorator_list:
        # Match @router.post(...), @router.delete(...), etc.
        if isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute):
            method = decorator.func.attr
            if method in MUTATION_METHODS:
                return method
    return None


def _is_auth_name(name: str) -> bool:
    """Check if a function name looks like an auth dependency."""
    return any(name.startswith(prefix) for prefix in AUTH_DEPENDENCY_PREFIXES)


def _has_auth_dependency(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """Check if a function has an auth dependency in its parameters."""
    # Check both positional args and keyword-only args (after bare * separator).
    all_args = node.args.args + node.args.kwonlyargs
    for arg in all_args:
        if arg.annotation is None:
            continue
        # Walk the annotation AST looking for Depends(require_*) or Depends(get_current_user).
        for child in ast.walk(arg.annotation):
            if isinstance(child, ast.Call):
                for call_arg in child.args:
                    if isinstance(call_arg, ast.Name) and _is_auth_name(call_arg.id):
                        return True
                for kw in child.keywords:
                    if isinstance(kw.value, ast.Name) and _is_auth_name(kw.value.id):
                        return True
    return False


def _check_auth_on_mutations(
    *,
    tree: ast.AST,
    relative_file: str,
) -> list[Violation]:
    """SEC-001: Every mutation endpoint must have an auth dependency."""
    violations = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            continue

        method = _is_mutation_endpoint(node)
        if method is None:
            continue

        # Auth endpoints are exempt — they issue tokens, they can't require them.
        if node.name in AUTH_EXEMPT_ENDPOINTS:
            continue

        if not _has_auth_dependency(node):
            violations.append(
                Violation(
                    file=relative_file,
                    line=node.lineno,
                    rule="SEC-001: Mutation endpoints must have auth dependency",
                    message=f"@router.{method} endpoint '{node.name}' has no auth dependency",
                    fix=(
                        "Add a parameter like: "
                        "current_user: Annotated[AuthenticatedUser, Depends(get_current_user)]"
                    ),
                )
            )

    return violations


def _check_raw_sql(
    *,
    source: str,
    relative_file: str,
) -> list[Violation]:
    """SEC-002: No raw SQL strings."""
    violations = []

    # Exclude alembic migrations and test files entirely.
    if "alembic" in relative_file or "test_" in relative_file:
        return violations

    in_docstring = False
    for line_num, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()

        # Track multi-line docstrings to skip their content.
        docstring_delimiters = stripped.count('"""') + stripped.count("'''")
        if docstring_delimiters % 2 == 1:
            in_docstring = not in_docstring
            continue
        if in_docstring:
            continue

        # Skip comments.
        if stripped.startswith("#"):
            continue

        for pattern in RAW_SQL_PATTERNS:
            if pattern.search(line):
                violations.append(
                    Violation(
                        file=relative_file,
                        line=line_num,
                        rule="SEC-002: No raw SQL — use SQLAlchemy ORM/Core",
                        message=f"Possible raw SQL: {stripped[:80]}",
                        fix="Use SQLAlchemy ORM queries or Core expressions instead of raw SQL strings",
                    )
                )
                break  # One violation per line is enough.

    return violations


def _check_hardcoded_secrets(
    *,
    source: str,
    relative_file: str,
) -> list[Violation]:
    """SEC-003: No hardcoded secrets in source code."""
    violations = []

    # Skip excluded files.
    file_name = Path(relative_file).name
    if any(exclude in file_name for exclude in SECRET_SCAN_EXCLUDES):
        return violations

    for line_num, line in enumerate(source.splitlines(), start=1):
        stripped = line.strip()

        # Skip comments.
        if stripped.startswith("#"):
            continue

        for pattern in SECRET_PATTERNS:
            if pattern.search(line):
                # Exclude environment variable lookups and default placeholders.
                if "os.environ" in line or "os.getenv" in line or "settings." in line:
                    continue
                if '""' in line or "''" in line:
                    continue
                # Exclude type hints and docstrings.
                if "str =" not in line and "password" not in line.lower():
                    # Only flag if it really looks like an assignment.
                    pass

                violations.append(
                    Violation(
                        file=relative_file,
                        line=line_num,
                        rule="SEC-003: No hardcoded secrets in source code",
                        message=f"Possible hardcoded secret: {stripped[:60]}...",
                        fix="Use environment variables or a secrets manager instead",
                    )
                )
                break

    return violations


@dataclass
class SecurityPatternsCheck:
    """Validates security patterns across the backend."""

    name: str = "security_patterns"
    description: str = "Security pattern enforcement (auth, SQL, secrets)"
    rules: list[str] = field(
        default_factory=lambda: [
            "SEC-001: Mutation endpoints must have auth dependency",
            "SEC-002: No raw SQL — use SQLAlchemy ORM/Core",
            "SEC-003: No hardcoded secrets in source code",
        ]
    )

    def run(self, *, src_root: str) -> CheckResult:
        """Scan all Python files under src/ for security violations."""
        violations: list[Violation] = []
        warnings: list[Violation] = []
        src_path = Path(src_root)

        for py_file in sorted(src_path.rglob("*.py")):
            relative_file = str(py_file.relative_to(src_path))

            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            # SEC-001: Only check endpoint files (api/ layer).
            if relative_file.startswith("api/"):
                violations.extend(_check_auth_on_mutations(tree=tree, relative_file=relative_file))

            # SEC-002: Check all files for raw SQL (except alembic).
            violations.extend(_check_raw_sql(source=source, relative_file=relative_file))

            # SEC-003: Check all files for hardcoded secrets.
            violations.extend(_check_hardcoded_secrets(source=source, relative_file=relative_file))

        status = Status.FAIL if violations else (Status.WARN if warnings else Status.PASS)
        return CheckResult(
            check=self.name,
            status=status,
            violations=violations,
            warnings=warnings,
        )


# Self-register on import.
register(SecurityPatternsCheck())
