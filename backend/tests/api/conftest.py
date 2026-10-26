"""Shared fixtures for app.api tests.

Each test gets an isolated SQLite file (via FINALLY_DB_PATH, same pattern as
tests/db/conftest.py) and a freshly built FastAPI app (its own PriceCache
and market data source — never the module-level `app.main.app` singleton),
so tests never leak state into each other. MASSIVE_API_KEY is explicitly
unset so `create_market_data_source` always picks the simulator (no
network calls) regardless of the host environment.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    path = tmp_path / "finally_test.db"
    monkeypatch.setenv("FINALLY_DB_PATH", str(path))
    monkeypatch.delenv("MASSIVE_API_KEY", raising=False)
    yield path


@pytest.fixture
def app(db_path, tmp_path):
    from app.main import create_app

    # Point at a directory that doesn't exist so we also exercise the
    # guarded "no static build available" startup path used in local dev.
    return create_app(static_dir=tmp_path / "no-static-build-here")


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        yield test_client
