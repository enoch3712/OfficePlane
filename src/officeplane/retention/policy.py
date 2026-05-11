"""Retention policy logic — compute start_at and disposition_due_at."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


def compute_start_at(policy_start_trigger: str, document: dict[str, Any]) -> datetime:
    """Return the policy's effective start datetime for a document."""
    if policy_start_trigger == "created_at":
        v = document.get("created_at")
        if isinstance(v, datetime):
            return v
        if isinstance(v, str):
            # ISO-8601
            return datetime.fromisoformat(v.replace("Z", "+00:00"))
    if policy_start_trigger == "status_approved":
        # We don't track approval-time globally yet — fall back to now
        return datetime.now(tz=timezone.utc)
    # manual or unknown
    return datetime.now(tz=timezone.utc)


def compute_due_at(start_at: datetime, duration_days: int) -> datetime:
    return start_at + timedelta(days=duration_days)
