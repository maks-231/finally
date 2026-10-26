"""SQLite connection management with lazy schema initialization.

Per PLAN.md §7, there is no migration framework: the backend checks for the
database on first use and creates/seeds it if needed. This module implements
that by making initialization idempotent (CREATE TABLE IF NOT EXISTS, seed
rows only inserted when absent) and running it every time a connection is
opened. For a single-user, low-throughput trading simulator the cost of that
check is negligible, and it keeps the design simple: there's no separate
"has this process already initialized this path" flag to get out of sync.

The DB path is read from the FINALLY_DB_PATH environment variable on every
call to `get_db_path()` (not cached at import time), so tests can point it at
an isolated temp file per test by setting the env var before calling into
this package.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from .schema import CREATE_INDEX_STATEMENTS, CREATE_TABLE_STATEMENTS
from .seed import seed_if_empty

# backend/app/db/connection.py -> parents[3] is the repo root.
_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DB_PATH = _REPO_ROOT / "db" / "finally.db"


def get_db_path() -> Path:
    """Resolve the SQLite database file path.

    Reads FINALLY_DB_PATH from the environment on every call. If unset or
    empty, defaults to <repo-root>/db/finally.db.
    """
    override = os.environ.get("FINALLY_DB_PATH", "").strip()
    return Path(override) if override else DEFAULT_DB_PATH


def _initialize(conn: sqlite3.Connection) -> None:
    """Create tables/indexes if missing and seed default data if empty."""
    for statement in CREATE_TABLE_STATEMENTS:
        conn.execute(statement)
    for statement in CREATE_INDEX_STATEMENTS:
        conn.execute(statement)
    seed_if_empty(conn)
    conn.commit()


def init_db(db_path: Path | str | None = None) -> None:
    """Explicitly initialize the database at `db_path` (or the resolved default).

    Idempotent: safe to call any number of times. Mainly useful for an
    explicit startup hook or in tests that want to assert idempotency without
    going through the repository layer.
    """
    path = Path(db_path) if db_path is not None else get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    try:
        _initialize(conn)
    finally:
        conn.close()


@contextmanager
def get_connection() -> Iterator[sqlite3.Connection]:
    """Open a connection to the SQLite database, lazily initializing it first.

    Ensures the `db/` directory exists, creates any missing tables/indexes,
    and seeds default data if empty — then yields a connection with
    `row_factory = sqlite3.Row` and manual (non-legacy) transaction control
    (`isolation_level = None`), so callers issue explicit BEGIN/COMMIT/
    ROLLBACK when they need multi-statement atomicity (see
    `repository.execute_trade`), and plain `commit()` after single-statement
    writes otherwise.

    Closes the connection on exit regardless of how the `with` block exits.
    """
    path = get_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.isolation_level = None
    try:
        _initialize(conn)
        yield conn
    finally:
        conn.close()
