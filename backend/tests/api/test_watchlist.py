"""Tests for /api/watchlist* (PLAN.md §8)."""

from __future__ import annotations

from app import db

DEFAULT_TICKERS = {"AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"}


def test_get_watchlist_returns_seeded_tickers_with_live_prices(client):
    response = client.get("/api/watchlist")
    assert response.status_code == 200
    body = response.json()

    tickers = {entry["ticker"] for entry in body}
    assert tickers == DEFAULT_TICKERS
    for entry in body:
        assert entry["price"] is not None
        assert entry["direction"] in ("up", "down", "flat")


def test_add_ticker_updates_db_and_source(client, app):
    response = client.post("/api/watchlist", json={"ticker": "pypl"})
    assert response.status_code == 200
    assert response.json() == {"ticker": "PYPL", "added": True}

    assert "PYPL" in db.get_watchlist()
    assert "PYPL" in app.state.market_source.get_tickers()
    assert app.state.price_cache.get_price("PYPL") is not None

    watchlist = client.get("/api/watchlist").json()
    assert any(entry["ticker"] == "PYPL" for entry in watchlist)


def test_add_duplicate_ticker_is_idempotent_noop(client):
    first = client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert first.status_code == 200
    assert first.json() == {"ticker": "AAPL", "added": False}

    # Still exactly one AAPL entry on the watchlist afterward.
    tickers = db.get_watchlist()
    assert tickers.count("AAPL") == 1


def test_remove_ticker_updates_db_and_source(client, app):
    response = client.delete("/api/watchlist/AAPL")
    assert response.status_code == 200
    assert response.json() == {"ticker": "AAPL", "removed": True}

    assert "AAPL" not in db.get_watchlist()
    assert "AAPL" not in app.state.market_source.get_tickers()
    assert app.state.price_cache.get("AAPL") is None

    watchlist = client.get("/api/watchlist").json()
    assert all(entry["ticker"] != "AAPL" for entry in watchlist)


def test_remove_nonexistent_ticker_returns_404(client):
    response = client.delete("/api/watchlist/ZZZZ")
    assert response.status_code == 404


def test_add_ticker_lowercase_is_normalized(client):
    response = client.post("/api/watchlist", json={"ticker": "  tsm  "})
    assert response.status_code == 200
    assert response.json()["ticker"] == "TSM"
    assert "TSM" in db.get_watchlist()
