"""Shared fixtures for app.db tests.

Every test gets its own temp SQLite file and points FINALLY_DB_PATH at it, so
tests never share state (per the task's isolation requirement). `get_db_path`
reads the env var fresh on every call (no module-level caching), so no
module reload is needed between tests.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    """Point FINALLY_DB_PATH at an isolated temp file for this test only."""
    path = tmp_path / "finally_test.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(path))
    yield path


@pytest.fixture
def db(db_path):
    """`app.db` package, pointed at the isolated temp db path for this test.

    Returns the module so tests can call its public API (e.g.
    `db.execute_trade(...)`) exactly like downstream engineers will.
    """
    import app.db as db_module

    return db_module
