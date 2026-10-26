"""Schema creation and seed-data tests."""

from __future__ import annotations

import sqlite3


def test_fresh_db_creates_all_six_tables(db, db_path):
    db.init_db(db_path)
    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        table_names = {row[0] for row in rows}
    finally:
        conn.close()

    expected = {
        "users_profile",
        "watchlist",
        "positions",
        "trades",
        "portfolio_snapshots",
        "chat_messages",
    }
    assert expected.issubset(table_names)


def test_fresh_db_seeds_default_user_and_watchlist(db, db_path):
    db.init_db(db_path)
    assert db.get_cash_balance() == 10000.0
    watchlist = db.get_watchlist()
    assert watchlist == ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"]


def test_init_db_twice_does_not_duplicate_or_error(db, db_path):
    db.init_db(db_path)
    db.init_db(db_path)  # must not raise, must not duplicate rows

    conn = sqlite3.connect(db_path)
    try:
        (user_count,) = conn.execute("SELECT COUNT(*) FROM users_profile").fetchone()
        (watchlist_count,) = conn.execute("SELECT COUNT(*) FROM watchlist").fetchone()
    finally:
        conn.close()

    assert user_count == 1
    assert watchlist_count == 10
    assert db.get_cash_balance() == 10000.0


def test_lazy_init_via_get_connection_without_explicit_init_db(db):
    # No explicit init_db() call — repository functions should lazily
    # initialize on first use.
    assert db.get_cash_balance() == 10000.0
    assert len(db.get_watchlist()) == 10


def test_seed_does_not_repopulate_watchlist_after_user_clears_it(db):
    db.init_db()
    for ticker in list(db.get_watchlist()):
        db.remove_from_watchlist(ticker)
    assert db.get_watchlist() == []

    # Re-running init (e.g. backend restart) should not repopulate a
    # watchlist the user intentionally emptied.
    db.init_db()
    assert db.get_watchlist() == []
