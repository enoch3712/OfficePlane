"""Resolve ``${steps.<alias>.outputs.<dotted.path>}`` references in pipeline step inputs.

Also supports ``${parameters.<key>}`` for top-level pipeline parameters.
"""
from __future__ import annotations

import re
from typing import Any

REF_RE = re.compile(r"\$\{([a-zA-Z0-9_.-]+)\}")


def _walk(value: Any, ctx: dict[str, Any]) -> Any:
    if isinstance(value, str):
        return _resolve_str(value, ctx)
    if isinstance(value, list):
        return [_walk(v, ctx) for v in value]
    if isinstance(value, dict):
        return {k: _walk(v, ctx) for k, v in value.items()}
    return value


def _resolve_str(s: str, ctx: dict[str, Any]) -> Any:
    """If the whole string is a single ${ref}, replace with the typed value.
    Otherwise treat refs as templated substrings (string-interpolated)."""
    m = REF_RE.fullmatch(s.strip())
    if m:
        value = _lookup(m.group(1), ctx)
        return value  # may be any type
    # Otherwise multi-token substring substitution → string result
    def _sub(match: re.Match) -> str:
        v = _lookup(match.group(1), ctx)
        if v is None:
            return ""
        if isinstance(v, (dict, list)):
            import json
            return json.dumps(v)
        return str(v)
    return REF_RE.sub(_sub, s)


def _lookup(path: str, ctx: dict[str, Any]) -> Any:
    parts = path.split(".")
    cur: Any = ctx
    for part in parts:
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                idx = int(part)
                cur = cur[idx]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return cur


def resolve(inputs: Any, *, parameters: dict[str, Any], step_outputs: dict[str, dict[str, Any]]) -> Any:
    """Resolve refs across `inputs`. `step_outputs` is keyed by alias.

    Available reference roots:
      - parameters.<key>
      - steps.<alias>.outputs.<dotted.path>
    """
    ctx = {"parameters": parameters, "steps": {a: {"outputs": o} for a, o in step_outputs.items()}}
    return _walk(inputs, ctx)
