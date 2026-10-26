"""Default seed data (PLAN.md §7).

Seeding is idempotent: `seed_if_empty` checks for existing rows before
inserting, so it is always safe to call on every lazy-init pass, not just on
a brand-new database file.
"""

from __future__ import annotations

import sqlite3

from ._util import new_id, now_iso

DEFAULT_USER_ID = "default"
DEFAULT_CASH_BALANCE = 10000.0

DEFAULT_WATCHLIST_TICKERS: list[str] = [
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "JPM",
    "V",
    "NFLX",
]


def seed_if_empty(conn: sqlite3.Connection) -> None:
    """Seed the default user profile and default watchlist exactly once.

    The presence of the "default" `users_profile` row is the single signal
    for "has this database already been seeded". If it exists, this is a
    no-op — in particular, a user who has since cleared their watchlist down
    to zero rows will NOT have it silently repopulated on the next lazy-init
    pass (which runs on every `get_connection()` call). Seeding only happens
    once, atomically, when the profile row is first created.

    Does not commit — caller controls the transaction.
    """
    existing_profile = conn.execute(
        "SELECT 1 FROM users_profile WHERE id = ?", (DEFAULT_USER_ID,)
    ).fetchone()
    if existing_profile is not None:
        return

    conn.execute(
        "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        (DEFAULT_USER_ID, DEFAULT_CASH_BALANCE, now_iso()),
    )
    added_at = now_iso()
    conn.executemany(
        "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
        [
            (new_id(), DEFAULT_USER_ID, ticker, added_at)
            for ticker in DEFAULT_WATCHLIST_TICKERS
        ],
    )
