"""Security pattern checks for OfficePlane.

Rules:
  SEC-001: No hardcoded secrets (API keys, passwords, tokens)
  SEC-002: No raw SQL queries (use Prisma/ORM)
  SEC-003: No path traversal in file operations
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from checks import CheckResult, Status, Violation, register

_SECRET_PATTERNS = [
    re.compile(r'(?:api[_-]?key|password|secret|token)\s*=\s*["\'][^"\']{8,}["\']', re.IGNORECASE),
    re.compile(r'(?:GOOGLE_API_KEY|DATABASE_URL|REDIS_URL)\s*=\s*["\'][^"\']+["\']'),
    re.compile(r'sk-[a-zA-Z0-9]{20,}'),
    re.compile(r'AIza[a-zA-Z0-9_-]{35}'),
]

_RAW_SQL_PATTERNS = [
    re.compile(r'(?:execute|executemany)\s*\(\s*["\'](?:SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)', re.IGNORECASE),
    re.compile(r'cursor\.\w+\s*\(\s*f["\']', re.IGNORECASE),
]

_PATH_TRAVERSAL = re.compile(r'\.\.[/\\]')


class SecurityPatternCheck:
    name = "security_patterns"
    description = "Check for hardcoded secrets, raw SQL, and path traversal"
    rules = ["SEC-001: No hardcoded secrets", "SEC-002: No raw SQL", "SEC-003: No path traversal in file ops"]

    def run(self, *, src_root: str) -> CheckResult:
        violations: list[Violation] = []
        warnings: list[Violation] = []

        for py_file in Path(src_root).rglob("*.py"):
            rel = str(py_file.relative_to(Path(src_root).parent))
            try:
                content = py_file.read_text()
            except (OSError, UnicodeDecodeError):
                continue

            for i, line in enumerate(content.splitlines(), 1):
                # Skip comments and test files
                stripped = line.strip()
                if stripped.startswith("#") or "test" in str(py_file).lower():
                    continue

                # SEC-001: Hardcoded secrets
                for pattern in _SECRET_PATTERNS:
                    if pattern.search(line):
                        # Skip os.environ and config patterns
                        if "os.environ" in line or "os.getenv" in line or "settings." in line:
                            continue
                        violations.append(Violation(
                            file=rel, line=i, rule="SEC-001",
                            message=f"Possible hardcoded secret: {stripped[:80]}",
                            fix="Use environment variables via os.environ or settings",
                        ))

                # SEC-002: Raw SQL
                for pattern in _RAW_SQL_PATTERNS:
                    if pattern.search(line):
                        violations.append(Violation(
                            file=rel, line=i, rule="SEC-002",
                            message="Raw SQL query detected",
                            fix="Use Prisma ORM or parameterized queries",
                        ))

                # SEC-003: Path traversal in file operations
                if any(op in line for op in ["open(", "Path(", "os.path.join"]):
                    if _PATH_TRAVERSAL.search(line):
                        warnings.append(Violation(
                            file=rel, line=i, rule="SEC-003",
                            message="Potential path traversal pattern",
                            fix="Validate and sanitize file paths before use",
                        ))

        status = Status.FAIL if violations else (Status.WARN if warnings else Status.PASS)
        return CheckResult(check=self.name, status=status, violations=violations, warnings=warnings)


register(SecurityPatternCheck())
