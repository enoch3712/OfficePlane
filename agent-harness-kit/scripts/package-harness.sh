#!/usr/bin/env bash
# Package the agent harness as a portable zip kit.
#
# Produces: agent-harness-kit.zip
# Contents: all harness files with template values ({{FRONTEND_DIR}} etc.)
#           ready for /setup-harness to configure on a new project.
#
# Usage:
#   ./scripts/package-harness.sh
#   ./scripts/package-harness.sh --output /path/to/output.zip

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OUTPUT="${2:-$PROJECT_ROOT/agent-harness-kit.zip}"

# Work from a temp dir so zip paths are clean
TMPDIR=$(mktemp -d)
KITDIR="$TMPDIR/agent-harness-kit"
mkdir -p "$KITDIR"

echo "Building harness kit..."

# --- Copy harness files ---

# Config (with template slug — the recipient will configure this)
cp "$PROJECT_ROOT/harness.config.sh" "$KITDIR/harness.config.sh"
# Reset to template defaults
sed -i \
  -e 's/HARNESS_PROJECT_SLUG=.*/HARNESS_PROJECT_SLUG="my-project"/' \
  -e 's/BACKEND_DIR=.*/BACKEND_DIR="backend"/' \
  -e 's/BACKEND_SERVICE=.*/BACKEND_SERVICE="backend"/' \
  -e 's/FRONTEND_DIR=.*/FRONTEND_DIR="frontend"/' \
  "$KITDIR/harness.config.sh"

# CLAUDE template
cp "$PROJECT_ROOT/CLAUDE.template.md" "$KITDIR/CLAUDE.template.md"

# .claude/
mkdir -p "$KITDIR/.claude/agents"
mkdir -p "$KITDIR/.claude/hooks"
mkdir -p "$KITDIR/.claude/skills"

# Hooks
cp "$PROJECT_ROOT/.claude/hooks/quality-gate.sh" "$KITDIR/.claude/hooks/"
cp "$PROJECT_ROOT/.claude/hooks/session-start.sh" "$KITDIR/.claude/hooks/"
chmod +x "$KITDIR/.claude/hooks/"*.sh

# settings.json — ensure placeholder is present (not current project's value)
cp "$PROJECT_ROOT/.claude/settings.json" "$KITDIR/.claude/settings.json"
# Ensure FRONTEND_DIR placeholder is set (not a resolved value)
sed -i 's|"Bash(cd [^)]*\*)"|"Bash(cd {{FRONTEND_DIR}} *)"|g' "$KITDIR/.claude/settings.json"

# Agents (all 6)
for agent in arch-guardian ddd-solid-reviewer entropy-sweeper fsd-guardian security-auditor test-inspector; do
  cp "$PROJECT_ROOT/.claude/agents/${agent}.md" "$KITDIR/.claude/agents/"
done

# Skills — harness core (universal)
for skill in dev-loop validate review-all review-arch review-ddd review-fsd review-security review-tests entropy-sweep harness setup-harness; do
  mkdir -p "$KITDIR/.claude/skills/${skill}"
  cp "$PROJECT_ROOT/.claude/skills/${skill}/SKILL.md" "$KITDIR/.claude/skills/${skill}/"
done

# Skills — reference (with supporting files)
for skill in ddd-architect fsd-architect uv-package-manager; do
  cp -r "$PROJECT_ROOT/.claude/skills/${skill}" "$KITDIR/.claude/skills/"
done

# checks/
mkdir -p "$KITDIR/checks"
for f in __init__.py __main__.py layer_deps.py security_patterns.py naming_consistency.py \
         file_limits.py named_args.py pattern_divergence.py port_coverage.py meta.py test_coverage.py; do
  [ -f "$PROJECT_ROOT/checks/$f" ] && cp "$PROJECT_ROOT/checks/$f" "$KITDIR/checks/"
done

# domain_terms.py — include as an empty template (project-specific vocabulary)
cat > "$KITDIR/checks/domain_terms.py" << 'PYEOF'
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
PYEOF

# scripts/
mkdir -p "$KITDIR/scripts"
for f in check-all.sh check-fsd.sh setup-hooks.sh package-harness.sh; do
  [ -f "$PROJECT_ROOT/scripts/$f" ] && cp "$PROJECT_ROOT/scripts/$f" "$KITDIR/scripts/"
done
chmod +x "$KITDIR/scripts/"*.sh

# .githooks/
mkdir -p "$KITDIR/.githooks"
cp "$PROJECT_ROOT/.githooks/pre-commit" "$KITDIR/.githooks/"
chmod +x "$KITDIR/.githooks/pre-commit"

# docs/ — design and references only (no project-specific adr/review/exec-plans)
mkdir -p "$KITDIR/docs/design"
mkdir -p "$KITDIR/docs/references"
cp "$PROJECT_ROOT/docs/design/core-beliefs.md" "$KITDIR/docs/design/"
cp "$PROJECT_ROOT/docs/design/enforcement-architecture.md" "$KITDIR/docs/design/"
[ -f "$PROJECT_ROOT/docs/design/index.md" ] && cp "$PROJECT_ROOT/docs/design/index.md" "$KITDIR/docs/design/"
for ref in claude-code-agents.md claude-code-hooks.md claude-code-platform.md harness-engineering-openai.md; do
  [ -f "$PROJECT_ROOT/docs/references/$ref" ] && cp "$PROJECT_ROOT/docs/references/$ref" "$KITDIR/docs/references/"
done

# --- Zip ---
cd "$TMPDIR"
zip -r "$OUTPUT" agent-harness-kit/ -x "*.DS_Store" -x "__pycache__/*" -x "*.pyc"

rm -rf "$TMPDIR"

echo ""
echo "✓ Harness kit packaged: $OUTPUT"
echo ""
echo "Contents:"
unzip -l "$OUTPUT" | tail -n +4 | head -n -2 | awk '{print "  " $NF}'
echo ""
echo "Developer onboarding:"
echo "  1. Unzip into project root: unzip agent-harness-kit.zip && cp -r agent-harness-kit/. ."
echo "  2. Open Claude Code in the project"
echo "  3. Run: /setup-harness"
