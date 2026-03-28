"""Unified enforcement checks for architecture, security, and code quality.

Run all checks:
    python -m checks

Run a specific check:
    python -m checks --check=security_patterns

JSON output for agent consumption:
    python -m checks --json

List all rules:
    python -m checks --list-rules
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Protocol


class Status(enum.Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


@dataclass(frozen=True)
class Violation:
    file: str
    line: int
    rule: str
    message: str
    fix: str

    def to_dict(self) -> dict[str, str | int]:
        return {
            "file": self.file,
            "line": self.line,
            "rule": self.rule,
            "message": self.message,
            "fix": self.fix,
        }

    def format_human(self) -> str:
        return (
            f"  VIOLATION: {self.file}:{self.line} — {self.message}\n"
            f"    Rule: {self.rule}\n"
            f"    Fix: {self.fix}"
        )


@dataclass
class CheckResult:
    check: str
    status: Status
    violations: list[Violation] = field(default_factory=list)
    warnings: list[Violation] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "check": self.check,
            "status": self.status.value,
            "violations": [v.to_dict() for v in self.violations],
            "warnings": [v.to_dict() for v in self.warnings],
        }

    def format_human(self) -> str:
        lines = [f"[{self.status.value}] {self.check}"]
        for v in self.violations:
            lines.append(v.format_human())
        for w in self.warnings:
            lines.append(w.format_human())
        lines.append(
            f"--- {self.check}: {len(self.violations)} violations, {len(self.warnings)} warnings ---"
        )
        return "\n".join(lines)


class Check(Protocol):
    name: str
    description: str
    rules: list[str]

    def run(self, *, src_root: str) -> CheckResult: ...


_registry: dict[str, Check] = {}


def register(check: Check) -> None:
    _registry[check.name] = check


def get_check(name: str) -> Check | None:
    return _registry.get(name)


def get_all_checks() -> dict[str, Check]:
    return dict(_registry)


def run_all(*, src_root: str) -> list[CheckResult]:
    results = []
    for check in _registry.values():
        results.append(check.run(src_root=src_root))
    return results
