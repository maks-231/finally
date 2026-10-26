"""Shared fixtures for app.llm tests (same isolation pattern as
tests/db/conftest.py): an isolated SQLite file per test, plus a fresh
PriceCache for tests that exercise `app.llm.prompt`.
"""

from __future__ import annotations

import pytest


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "finally_test.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(path))
    yield path


@pytest.fixture
def db(db_path):
    import app.db as db_module

    return db_module


@pytest.fixture
def price_cache():
    from app.market import PriceCache

    return PriceCache()
