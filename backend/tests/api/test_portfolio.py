"""Tests for /api/portfolio* (PLAN.md §7, §8).

Trade prices are always read from the running app's live PriceCache
(`app.state.price_cache`) rather than hardcoded seed values, since the
background GBM simulator may have already ticked the price forward by the
time a test runs.
"""

from __future__ import annotations

import pytest


def _price(app, ticker: str) -> float:
    price = app.state.price_cache.get_price(ticker)
    assert price is not None, f"expected {ticker} to have a seeded price"
    return price


def test_get_portfolio_initial_state(client):
    response = client.get("/api/portfolio")
    assert response.status_code == 200
    body = response.json()
    assert body["cash_balance"] == pytest.approx(10000.0)
    assert body["positions"] == []
    assert body["total_value"] == pytest.approx(10000.0)


def test_trade_buy_success(client, app):
    price = _price(app, "AAPL")

    response = client.post(
        "/api/portfolio/trade", json={"ticker": "aapl", "quantity": 10, "side": "buy"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["ticker"] == "AAPL"
    assert body["side"] == "buy"
    assert body["quantity"] == pytest.approx(10)
    assert body["price"] == pytest.approx(price)
    assert body["cash_balance"] == pytest.approx(10000.0 - 10 * price)
    assert body["position_quantity"] == pytest.approx(10)
    assert body["avg_cost"] == pytest.approx(price)

    portfolio = client.get("/api/portfolio").json()
    assert portfolio["cash_balance"] == pytest.approx(10000.0 - 10 * price)
    assert len(portfolio["positions"]) == 1
    position = portfolio["positions"][0]
    assert position["ticker"] == "AAPL"
    assert position["quantity"] == pytest.approx(10)
    assert position["avg_cost"] == pytest.approx(price)
    assert position["market_value"] == pytest.approx(position["quantity"] * position["current_price"])
    expected_pnl = position["market_value"] - position["quantity"] * position["avg_cost"]
    assert position["unrealized_pnl"] == pytest.approx(expected_pnl)
    assert portfolio["total_value"] == pytest.approx(
        portfolio["cash_balance"] + position["market_value"]
    )


def test_trade_buy_weighted_avg_cost(client, app):
    """Buying the same ticker twice recomputes avg_cost as a weighted average."""
    first_price = _price(app, "MSFT")
    first = client.post(
        "/api/portfolio/trade", json={"ticker": "MSFT", "quantity": 4, "side": "buy"}
    )
    assert first.status_code == 200
    assert first.json()["avg_cost"] == pytest.approx(first_price)

    second_price = _price(app, "MSFT")
    second = client.post(
        "/api/portfolio/trade", json={"ticker": "MSFT", "quantity": 6, "side": "buy"}
    )
    assert second.status_code == 200
    expected_avg_cost = (first_price * 4 + second_price * 6) / 10
    assert second.json()["avg_cost"] == pytest.approx(expected_avg_cost)
    assert second.json()["position_quantity"] == pytest.approx(10)


def test_trade_sell_closes_position(client, app):
    _price(app, "GOOGL")  # ensure the ticker has a seeded price before trading
    buy = client.post(
        "/api/portfolio/trade", json={"ticker": "GOOGL", "quantity": 5, "side": "buy"}
    )
    assert buy.status_code == 200

    sell = client.post(
        "/api/portfolio/trade", json={"ticker": "GOOGL", "quantity": 5, "side": "sell"}
    )
    assert sell.status_code == 200
    body = sell.json()
    assert body["position_quantity"] == pytest.approx(0.0)
    assert body["avg_cost"] is None

    portfolio = client.get("/api/portfolio").json()
    assert portfolio["positions"] == []


def test_trade_buy_insufficient_cash_rejected(client):
    response = client.post(
        "/api/portfolio/trade",
        json={"ticker": "AAPL", "quantity": 1_000_000, "side": "buy"},
    )
    assert response.status_code == 400
    assert "insufficient" in response.json()["detail"].lower()

    # Rejected trades must not mutate state.
    portfolio = client.get("/api/portfolio").json()
    assert portfolio["cash_balance"] == pytest.approx(10000.0)
    assert portfolio["positions"] == []


def test_trade_sell_oversell_rejected(client):
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "sell"}
    )
    assert response.status_code == 400
    assert "sell" in response.json()["detail"].lower()


def test_trade_unknown_ticker_rejected(client):
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "ZZZZ", "quantity": 1, "side": "buy"}
    )
    assert response.status_code == 400
    assert "no current price" in response.json()["detail"].lower()


def test_trade_invalid_side_rejected_by_validation(client):
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "hold"}
    )
    assert response.status_code == 422


def test_trade_nonpositive_quantity_rejected_by_validation(client):
    response = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 0, "side": "buy"}
    )
    assert response.status_code == 422


def test_portfolio_history_empty_initially(client):
    response = client.get("/api/portfolio/history")
    assert response.status_code == 200
    assert response.json() == []


def test_portfolio_history_records_snapshot_immediately_after_trade(client):
    trade = client.post(
        "/api/portfolio/trade", json={"ticker": "AAPL", "quantity": 1, "side": "buy"}
    )
    assert trade.status_code == 200
    expected_total_value = trade.json()["total_value"]

    history = client.get("/api/portfolio/history").json()
    assert len(history) == 1
    assert history[0]["total_value"] == pytest.approx(expected_total_value)
    assert "recorded_at" in history[0]
