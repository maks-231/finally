"""Tests for app.llm.mock's deterministic trigger rules (see module
docstring in app/llm/mock.py for the exact rule set).
"""

from __future__ import annotations

import pytest

from app.llm.mock import get_mock_response


def test_plain_message_has_no_actions():
    response = get_mock_response("What's my total portfolio value?")
    assert response.trades == []
    assert response.watchlist_changes == []
    assert "Mock mode" in response.message


def test_buy_trigger_with_shares_of_phrasing():
    response = get_mock_response("Please buy 10 shares of AAPL for me")
    assert len(response.trades) == 1
    trade = response.trades[0]
    assert trade.ticker == "AAPL"
    assert trade.side == "buy"
    assert trade.quantity == pytest.approx(10)
    assert response.watchlist_changes == []


def test_buy_trigger_without_shares_of_phrasing():
    response = get_mock_response("buy 2.5 TSLA")
    assert response.trades[0].ticker == "TSLA"
    assert response.trades[0].quantity == pytest.approx(2.5)


def test_sell_trigger_is_case_insensitive():
    response = get_mock_response("SELL 3 SHARES OF nflx")
    trade = response.trades[0]
    assert trade.ticker == "NFLX"
    assert trade.side == "sell"
    assert trade.quantity == pytest.approx(3)


def test_watchlist_add_trigger():
    response = get_mock_response("add PYPL to watchlist")
    assert response.trades == []
    assert len(response.watchlist_changes) == 1
    change = response.watchlist_changes[0]
    assert change.ticker == "PYPL"
    assert change.action == "add"


def test_watchlist_add_trigger_with_the():
    response = get_mock_response("Can you add pypl to the watchlist?")
    assert response.watchlist_changes[0].ticker == "PYPL"
    assert response.watchlist_changes[0].action == "add"


def test_watchlist_remove_trigger():
    response = get_mock_response("remove AAPL from watchlist")
    assert response.watchlist_changes[0].ticker == "AAPL"
    assert response.watchlist_changes[0].action == "remove"


def test_watchlist_remove_trigger_with_the():
    response = get_mock_response("remove AAPL from the watchlist please")
    assert response.watchlist_changes[0].action == "remove"


def test_unmatched_message_is_deterministic():
    first = get_mock_response("How is my portfolio doing today?")
    second = get_mock_response("How is my portfolio doing today?")
    assert first.message == second.message
    assert first.trades == second.trades == []
