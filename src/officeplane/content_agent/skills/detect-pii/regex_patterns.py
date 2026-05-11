"""Regex patterns for cheap deterministic PII detection.

Each pattern returns (category, span). The categories align with what the LLM
pass also uses so the two streams can be merged into a single redaction plan.
"""
from __future__ import annotations

import re

# Categories
EMAIL = "email"
PHONE = "phone"
SSN = "us_ssn"
IBAN = "iban"
CREDIT_CARD = "credit_card"
URL = "url"

_EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
_US_SSN_RE = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_PHONE_RE = re.compile(r"\b(?:\+?\d{1,3}[\s.-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s.-]?\d{3,4}[\s.-]?\d{3,4}\b")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
_CC_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def find_regex_pii(text: str) -> list[dict]:
    """Return a list of {category, value, start, end} for deterministic patterns."""
    out: list[dict] = []
    for cat, regex in (
        (EMAIL, _EMAIL_RE),
        (SSN, _US_SSN_RE),
        (PHONE, _PHONE_RE),
        (IBAN, _IBAN_RE),
    ):
        for m in regex.finditer(text):
            out.append({
                "category": cat,
                "value": m.group(0),
                "start": m.start(),
                "end": m.end(),
                "source": "regex",
                "confidence": 0.95 if cat in (EMAIL, SSN, IBAN) else 0.7,
            })

    # Credit card with Luhn check (skip obvious non-CC sequences)
    for m in _CC_RE.finditer(text):
        digits = "".join(ch for ch in m.group(0) if ch.isdigit())
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            out.append({
                "category": CREDIT_CARD,
                "value": m.group(0),
                "start": m.start(),
                "end": m.end(),
                "source": "regex",
                "confidence": 0.85,
            })

    return out


def _luhn_ok(digits: str) -> bool:
    s = 0
    for i, ch in enumerate(reversed(digits)):
        d = int(ch)
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        s += d
    return s % 10 == 0
