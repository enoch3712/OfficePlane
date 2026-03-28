"""TERM-001 through TERM-005: Domain terminology consistency.

Replace the APPROVED_TERMS and BANNED_TERMS below with your project's
domain vocabulary. Run /setup-harness for guidance on what to put here.

Run:
    uv run python -m checks --check=domain_terms
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from checks import CheckResult, Status, Violation, register

# Map banned terms to their approved replacements.
# Add your project's domain vocabulary here.
# Example: "fetch_agent": "get_agent"
BANNED_TERMS: dict[str, str] = {}

# Approved naming patterns (informational — not enforced as violations).
APPROVED_TERMS: list[str] = []


@dataclass
class DomainTermsCheck:
    """Validates domain terminology consistency."""

    name: str = "domain_terms"
    description: str = "Domain terminology consistency"
    rules: list[str] = field(
        default_factory=lambda: [
            "TERM-001: Use approved domain terms (see BANNED_TERMS in checks/domain_terms.py)",
        ]
    )

    def run(self, *, src_root: str) -> CheckResult:
        """Scan Python files for banned domain terms."""
        if not BANNED_TERMS:
            return CheckResult(
                check=self.name,
                status=Status.PASS,
                violations=[],
                warnings=[],
            )

        violations: list[Violation] = []
        src_path = Path(src_root)

        for py_file in sorted(src_path.rglob("*.py")):
            try:
                source = py_file.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(py_file))
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                name: str | None = None
                if isinstance(node, ast.Name):
                    name = node.id
                elif isinstance(node, ast.Attribute):
                    name = node.attr
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    name = node.name

                if name and name in BANNED_TERMS:
                    violations.append(
                        Violation(
                            file=str(py_file.relative_to(src_path)),
                            line=getattr(node, "lineno", 0),
                            rule="TERM-001: Use approved domain terms",
                            message=f"Banned term '{name}' — use '{BANNED_TERMS[name]}' instead",
                            fix=f"Rename '{name}' to '{BANNED_TERMS[name]}'",
                        )
                    )

        status = Status.FAIL if violations else Status.PASS
        return CheckResult(
            check=self.name,
            status=status,
            violations=violations,
            warnings=[],
        )


register(DomainTermsCheck())
