"""Tests for app.llm.prompt (portfolio context + message list construction,
PLAN.md §9)."""

from __future__ import annotations

import pytest

from app.llm.prompt import build_messages, build_portfolio_context


def test_build_portfolio_context_empty_portfolio(db, price_cache):
    # Lazy DB init seeds the default 10-ticker watchlist (PLAN.md §7), but
    # nothing has a price in this fresh, unstarted PriceCache yet.
    context = build_portfolio_context(price_cache)
    assert context["cash_balance"] == pytest.approx(10000.0)
    assert context["positions"] == []
    assert context["total_portfolio_value"] == pytest.approx(10000.0)
    assert len(context["watchlist"]) == 10
    assert all(entry["price"] is None for entry in context["watchlist"])


def test_build_portfolio_context_includes_live_prices_and_pnl(db, price_cache):
    price_cache.update("AAPL", 100.0)
    db.execute_trade(ticker="AAPL", side="buy", quantity=10, price=100.0)
    price_cache.update("AAPL", 120.0)

    context = build_portfolio_context(price_cache)
    assert context["cash_balance"] == pytest.approx(10000.0 - 1000.0)
    assert len(context["positions"]) == 1
    position = context["positions"][0]
    assert position["ticker"] == "AAPL"
    assert position["current_price"] == pytest.approx(120.0)
    assert position["unrealized_pnl"] == pytest.approx(200.0)
    assert context["total_portfolio_value"] == pytest.approx(context["cash_balance"] + 10 * 120.0)


def test_build_portfolio_context_watchlist_prices(db, price_cache):
    # MSFT is already in the default seeded watchlist; just give it a price.
    price_cache.update("MSFT", 300.0)

    context = build_portfolio_context(price_cache)
    entry = next(e for e in context["watchlist"] if e["ticker"] == "MSFT")
    assert entry == {"ticker": "MSFT", "price": 300.0}


def test_build_portfolio_context_handles_missing_cache_price(db, price_cache):
    # A watched ticker with no price in the cache at all (e.g. the backend
    # just started and the simulator hasn't ticked yet).
    db.add_to_watchlist("ZZZZ")
    context = build_portfolio_context(price_cache)
    entry = next(e for e in context["watchlist"] if e["ticker"] == "ZZZZ")
    assert entry == {"ticker": "ZZZZ", "price": None}


def test_build_messages_includes_system_history_and_new_user_message(db, price_cache):
    db.append_chat_message("user", "Hi")
    db.append_chat_message("assistant", "Hello, how can I help?")

    messages = build_messages(price_cache, "Buy some AAPL")

    assert messages[0]["role"] == "system"
    assert "FinAlly" in messages[0]["content"]
    assert messages[1]["role"] == "system"
    assert "cash_balance" in messages[1]["content"]
    assert messages[2] == {"role": "user", "content": "Hi"}
    assert messages[3] == {"role": "assistant", "content": "Hello, how can I help?"}
    assert messages[-1] == {"role": "user", "content": "Buy some AAPL"}


def test_build_messages_limits_history_to_last_20(db, price_cache):
    for i in range(25):
        db.append_chat_message("user", f"msg-{i}")

    messages = build_messages(price_cache, "new message")
    # 2 system messages + 20 history turns + 1 new user message.
    history_messages = messages[2:-1]
    assert len(history_messages) == 20
    assert history_messages[0]["content"] == "msg-5"
    assert history_messages[-1]["content"] == "msg-24"
