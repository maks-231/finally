"""DDL for the FinAlly database schema.

This matches PLAN.md §7 exactly: six tables, all scoped by a `user_id` column
that defaults to "default" (single-user today, multi-user-ready later with no
schema migration needed). No migration framework is used anywhere in this
package — all CREATE statements are `IF NOT EXISTS` so re-running them against
an already-initialized database is always a safe no-op.
"""

from __future__ import annotations

CREATE_USERS_PROFILE = """
CREATE TABLE IF NOT EXISTS users_profile (
    id TEXT PRIMARY KEY,
    cash_balance REAL NOT NULL DEFAULT 10000.0,
    created_at TEXT NOT NULL
)
"""

CREATE_WATCHLIST = """
CREATE TABLE IF NOT EXISTS watchlist (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    added_at TEXT NOT NULL,
    UNIQUE (user_id, ticker)
)
"""

CREATE_POSITIONS = """
CREATE TABLE IF NOT EXISTS positions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    quantity REAL NOT NULL,
    avg_cost REAL NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (user_id, ticker)
)
"""

CREATE_TRADES = """
CREATE TABLE IF NOT EXISTS trades (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    ticker TEXT NOT NULL,
    side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    executed_at TEXT NOT NULL
)
"""

CREATE_PORTFOLIO_SNAPSHOTS = """
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    total_value REAL NOT NULL,
    recorded_at TEXT NOT NULL
)
"""

CREATE_CHAT_MESSAGES = """
CREATE TABLE IF NOT EXISTS chat_messages (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL DEFAULT 'default',
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT NOT NULL,
    actions TEXT,
    created_at TEXT NOT NULL
)
"""

# Order matters only in that tables with no cross-references can be created
# in any order; none of these six tables use FOREIGN KEY constraints (the
# user_id column is a plain string tag, not an FK), so order is unconstrained.
CREATE_TABLE_STATEMENTS: list[str] = [
    CREATE_USERS_PROFILE,
    CREATE_WATCHLIST,
    CREATE_POSITIONS,
    CREATE_TRADES,
    CREATE_PORTFOLIO_SNAPSHOTS,
    CREATE_CHAT_MESSAGES,
]

# Supplementary indexes for query patterns the repository layer uses
# frequently (lookups and ordering by user_id). Not specified in PLAN.md §7
# but purely additive — they don't change table shape or constraints.
CREATE_INDEX_STATEMENTS: list[str] = [
    "CREATE INDEX IF NOT EXISTS idx_trades_user_id ON trades (user_id)",
    "CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_user_recorded "
    "ON portfolio_snapshots (user_id, recorded_at)",
    "CREATE INDEX IF NOT EXISTS idx_chat_messages_user_created "
    "ON chat_messages (user_id, created_at)",
]
