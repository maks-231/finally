"""Tests for app.llm.schema (PLAN.md §9 structured-output contract)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.llm.schema import ChatResponse, TradeAction, WatchlistChange


def test_chat_response_defaults_to_empty_actions():
    response = ChatResponse(message="Hi")
    assert response.trades == []
    assert response.watchlist_changes == []


def test_chat_response_parses_full_payload():
    response = ChatResponse.model_validate(
        {
            "message": "Buying AAPL and watching PYPL.",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}],
            "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
        }
    )
    assert response.trades == [TradeAction(ticker="AAPL", side="buy", quantity=10)]
    assert response.watchlist_changes == [WatchlistChange(ticker="PYPL", action="add")]


def test_chat_response_requires_message():
    with pytest.raises(ValidationError):
        ChatResponse.model_validate({"trades": []})


def test_trade_action_rejects_invalid_side():
    with pytest.raises(ValidationError):
        TradeAction(ticker="AAPL", side="hold", quantity=1)


def test_watchlist_change_rejects_invalid_action():
    with pytest.raises(ValidationError):
        WatchlistChange(ticker="AAPL", action="watch")


def test_chat_response_model_validate_json_matches_llm_output_shape():
    raw = (
        '{"message": "Done.", "trades": [{"ticker": "msft", "side": "sell", '
        '"quantity": 2.5}], "watchlist_changes": []}'
    )
    response = ChatResponse.model_validate_json(raw)
    assert response.trades[0].ticker == "msft"
    assert response.trades[0].quantity == pytest.approx(2.5)
