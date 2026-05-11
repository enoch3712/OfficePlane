"""Minimal jsonlogic evaluator. Public spec: https://jsonlogic.com.

Supports: ==, !=, !, >, >=, <, <=, and, or, in, var (dotted path access),
+, -, *, /, missing, missing_some.
Sufficient for OfficePlane trigger filters; not a full implementation.
"""
from __future__ import annotations

from typing import Any


def apply(rule: Any, data: dict[str, Any] | None = None) -> Any:
    data = data or {}
    if not isinstance(rule, dict) or not rule:
        return rule
    if len(rule) != 1:
        # treat multi-key dict as object literal
        return {k: apply(v, data) for k, v in rule.items()}

    (op, args), = rule.items()
    if not isinstance(args, list):
        args = [args]

    if op == "var":
        return _var(args[0] if args else "", data, default=(args[1] if len(args) > 1 else None))
    if op == "==":
        return apply(args[0], data) == apply(args[1], data)
    if op == "!=":
        return apply(args[0], data) != apply(args[1], data)
    if op == "!":
        return not bool(apply(args[0], data))
    if op == ">":
        a, b = apply(args[0], data), apply(args[1], data)
        return (a is not None) and (b is not None) and a > b
    if op == ">=":
        a, b = apply(args[0], data), apply(args[1], data)
        return (a is not None) and (b is not None) and a >= b
    if op == "<":
        a, b = apply(args[0], data), apply(args[1], data)
        return (a is not None) and (b is not None) and a < b
    if op == "<=":
        a, b = apply(args[0], data), apply(args[1], data)
        return (a is not None) and (b is not None) and a <= b
    if op == "and":
        result = True
        for a in args:
            result = apply(a, data)
            if not result:
                return result
        return result
    if op == "or":
        result = False
        for a in args:
            result = apply(a, data)
            if result:
                return result
        return result
    if op == "in":
        needle = apply(args[0], data)
        haystack = apply(args[1], data)
        if isinstance(haystack, (list, tuple, str, set)):
            return needle in haystack
        return False
    if op == "missing":
        return [k for k in args if _var(k, data) in (None, "")]
    if op == "missing_some":
        min_required, keys = int(args[0]), args[1]
        present = sum(1 for k in keys if _var(k, data) not in (None, ""))
        return [] if present >= min_required else [k for k in keys if _var(k, data) in (None, "")]
    if op == "+":
        return sum(float(apply(a, data) or 0) for a in args)
    if op == "-":
        if len(args) == 1:
            return -float(apply(args[0], data) or 0)
        return float(apply(args[0], data) or 0) - float(apply(args[1], data) or 0)
    if op == "*":
        result = 1.0
        for a in args:
            result *= float(apply(a, data) or 0)
        return result
    if op == "/":
        a, b = float(apply(args[0], data) or 0), float(apply(args[1], data) or 1)
        return a / b if b else 0

    raise ValueError(f"unsupported jsonlogic op: {op}")


def _var(path: Any, data: dict[str, Any], default: Any = None) -> Any:
    if path == "" or path is None:
        return data
    if not isinstance(path, str):
        return path
    cur: Any = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        elif isinstance(cur, list):
            try:
                cur = cur[int(part)]
            except (ValueError, IndexError):
                return default
        else:
            return default
    return cur
