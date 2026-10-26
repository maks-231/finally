"""Watchlist add/remove tests."""

from __future__ import annotations


def test_default_watchlist_seeded(db):
    assert db.get_watchlist() == [
        "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX",
    ]


def test_add_new_ticker(db):
    added = db.add_to_watchlist("pypl")  # lowercase input
    assert added is True
    assert "PYPL" in db.get_watchlist()


def test_add_duplicate_ticker_is_noop_not_error(db):
    db.add_to_watchlist("PYPL")
    added_again = db.add_to_watchlist("PYPL")
    assert added_again is False
    assert db.get_watchlist().count("PYPL") == 1


def test_add_duplicate_case_insensitive(db):
    db.add_to_watchlist("pypl")
    added_again = db.add_to_watchlist("PYPL")
    assert added_again is False
    assert db.get_watchlist().count("PYPL") == 1


def test_remove_existing_ticker(db):
    removed = db.remove_from_watchlist("AAPL")
    assert removed is True
    assert "AAPL" not in db.get_watchlist()


def test_remove_nonexistent_ticker_returns_false(db):
    removed = db.remove_from_watchlist("ZZZZ")
    assert removed is False


def test_watchlist_isolated_per_user(db):
    db.add_to_watchlist("PYPL", user_id="alice")
    assert db.get_watchlist(user_id="alice") == ["PYPL"]
    assert "PYPL" not in db.get_watchlist()  # default user unaffected
