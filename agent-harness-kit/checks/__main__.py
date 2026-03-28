"""CLI entrypoint: uv run python -m checks [--check=name] [--json] [--list-rules]."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Import check modules to trigger registration.
# Add new checks here as they are built.
import checks.domain_terms  # noqa: F401
import checks.file_limits  # noqa: F401
import checks.layer_deps  # noqa: F401
import checks.meta  # noqa: F401
import checks.named_args  # noqa: F401
import checks.naming_consistency  # noqa: F401
import checks.pattern_divergence  # noqa: F401
import checks.port_coverage  # noqa: F401
import checks.security_patterns  # noqa: F401
import checks.test_coverage  # noqa: F401
from checks import CheckResult, Status, get_all_checks, get_check, run_all


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uv run python -m checks",
        description="Run architecture and quality enforcement checks.",
    )
    parser.add_argument(
        "--check",
        type=str,
        default=None,
        help="Run a single check by name (e.g., --check=layer_deps).",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON for agent consumption.",
    )
    parser.add_argument(
        "--list-rules",
        action="store_true",
        help="List all registered rules and exit.",
    )
    return parser


def _print_rules() -> None:
    """Print all registered rules across all checks."""
    checks = get_all_checks()
    if not checks:
        print("No checks registered.")
        return

    for check in checks.values():
        print(f"\n## {check.name} — {check.description}")
        for rule in check.rules:
            print(f"  {rule}")


def _print_results(
    *,
    results: list[CheckResult],
    json_output: bool,
) -> None:
    """Print results in human or JSON format."""
    if json_output:
        output = [r.to_dict() for r in results]
        print(json.dumps(output, indent=2))
        return

    for result in results:
        print(result.format_human())
        print()


def _resolve_src_root() -> str:
    """Find the src/ directory relative to the backend root."""
    # When run as `python -m checks` from agent_builder_backend/
    candidates = [
        Path.cwd() / "src",
        Path(__file__).parent.parent / "src",
    ]
    for candidate in candidates:
        if candidate.is_dir():
            return str(candidate)

    print("ERROR: Could not find src/ directory. Run from agent_builder_backend/.", file=sys.stderr)
    sys.exit(1)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    if args.list_rules:
        _print_rules()
        return

    src_root = _resolve_src_root()

    if args.check:
        check = get_check(args.check)
        if check is None:
            available = ", ".join(get_all_checks().keys())
            print(f"ERROR: Unknown check '{args.check}'. Available: {available}", file=sys.stderr)
            sys.exit(1)
        results = [check.run(src_root=src_root)]
    else:
        results = run_all(src_root=src_root)

    if not results:
        print("No checks registered. Add check modules to checks/__main__.py imports.")
        return

    _print_results(results=results, json_output=args.json_output)

    # Exit with non-zero if any check failed.
    has_failures = any(r.status == Status.FAIL for r in results)
    if has_failures:
        sys.exit(1)


if __name__ == "__main__":
    main()
