"""Small internal helpers shared across the db package."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone


def now_iso() -> str:
    """Current UTC time as an ISO-8601 string (microsecond precision).

    Used for all `*_at` / `*_created_at` / `recorded_at` columns so that
    ordering by the column lexically matches chronological order.
    """
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    """Generate a new UUID4 string for use as a TEXT PRIMARY KEY."""
    return str(uuid.uuid4())
