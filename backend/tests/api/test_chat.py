"""Tests for /api/chat (PLAN.md §8, §9).

No real network calls: real-LLM-path tests monkeypatch
`app.llm.client.completion` directly. Mock-mode tests exercise
`app.llm.mock.get_mock_response`'s deterministic trigger rules end-to-end
through the route (trade auto-execution, watchlist auto-execution, plain
replies, determinism).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from app import db


@pytest.fixture(autouse=True)
def _clean_llm_env(monkeypatch):
    """Every test starts with a clean slate for the two LLM-related env
    vars; individual tests opt into whichever combination they need.
    """
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MOCK", raising=False)


def _fake_completion_returning(content: str):
    def _fake_completion(**kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    return _fake_completion


# --------------------------------------------------------------------------
# GET /api/chat
# --------------------------------------------------------------------------


def test_get_chat_history_empty_initially(client):
    response = client.get("/api/chat")
    assert response.status_code == 200
    assert response.json() == []


def test_get_chat_history_returns_persisted_messages(client):
    db.append_chat_message("user", "hello")
    db.append_chat_message("assistant", "hi there", actions={"trades": [], "watchlist_changes": []})

    response = client.get("/api/chat")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 2
    assert body[0]["role"] == "user"
    assert body[0]["content"] == "hello"
    assert body[0]["actions"] is None
    assert body[1]["role"] == "assistant"
    assert body[1]["actions"] == {"trades": [], "watchlist_changes": []}


# --------------------------------------------------------------------------
# 503 when no API key configured and LLM_MOCK isn't "true"
# --------------------------------------------------------------------------


def test_post_chat_503_when_no_api_key_and_not_mocked(client):
    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 503
    assert "OPENROUTER_API_KEY" in response.json()["detail"]

    # The gate must reject before touching the DB: no chat history recorded.
    assert db.get_chat_messages() == []


def test_post_chat_503_even_with_llm_mock_false_explicitly(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "false")
    response = client.post("/api/chat", json={"message": "hello"})
    assert response.status_code == 503


def test_other_endpoints_unaffected_by_missing_api_key(client):
    # Sanity check: the 503 gate is scoped to POST /api/chat only.
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/portfolio").status_code == 200
    assert client.get("/api/watchlist").status_code == 200
    assert client.get("/api/chat").status_code == 200


# --------------------------------------------------------------------------
# LLM_MOCK=true deterministic trigger rules
# --------------------------------------------------------------------------


def test_mock_mode_plain_reply_has_no_actions(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    response = client.post("/api/chat", json={"message": "What's my portfolio worth?"})
    assert response.status_code == 200
    body = response.json()
    assert body["trades"] == []
    assert body["watchlist_changes"] == []
    assert "Mock mode" in body["message"]


def test_mock_mode_determinism(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    first = client.post("/api/chat", json={"message": "What's my portfolio worth?"})
    second = client.post("/api/chat", json={"message": "What's my portfolio worth?"})
    assert first.json()["message"] == second.json()["message"]


def test_mock_mode_trade_trigger_executes_buy(client, app, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    price = app.state.price_cache.get_price("AAPL")
    assert price is not None

    response = client.post("/api/chat", json={"message": "buy 10 shares of AAPL"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["trades"]) == 1
    trade = body["trades"][0]
    assert trade["success"] is True
    assert trade["ticker"] == "AAPL"
    assert trade["side"] == "buy"
    assert trade["quantity"] == pytest.approx(10)
    assert trade["price"] == pytest.approx(price)

    portfolio = client.get("/api/portfolio").json()
    assert any(p["ticker"] == "AAPL" and p["quantity"] == pytest.approx(10) for p in portfolio["positions"])


def test_mock_mode_trade_trigger_insufficient_cash_surfaces_failure(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    response = client.post("/api/chat", json={"message": "buy 999999 shares of AAPL"})
    assert response.status_code == 200
    body = response.json()
    assert len(body["trades"]) == 1
    trade = body["trades"][0]
    assert trade["success"] is False
    assert "insufficient" in trade["reason"].lower()

    # The failed trade must not have mutated portfolio state, and the chat
    # message must still have been persisted (one failed action doesn't
    # crash the flow).
    portfolio = client.get("/api/portfolio").json()
    assert portfolio["cash_balance"] == pytest.approx(10000.0)
    history = db.get_chat_messages()
    assert len(history) == 2
    assert history[1]["actions"]["trades"][0]["success"] is False


def test_mock_mode_sell_trigger(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    buy = client.post("/api/chat", json={"message": "buy 5 shares of AAPL"})
    assert buy.json()["trades"][0]["success"] is True

    sell = client.post("/api/chat", json={"message": "sell 5 shares of AAPL"})
    body = sell.json()
    assert body["trades"][0]["success"] is True
    assert body["trades"][0]["side"] == "sell"

    portfolio = client.get("/api/portfolio").json()
    assert portfolio["positions"] == []


def test_mock_mode_watchlist_add_trigger_updates_db_and_source(client, app, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    response = client.post("/api/chat", json={"message": "please add PYPL to watchlist"})
    assert response.status_code == 200
    body = response.json()
    assert body["watchlist_changes"] == [
        {"ticker": "PYPL", "action": "add", "success": True, "already_present": False}
    ]
    assert "PYPL" in db.get_watchlist()
    assert "PYPL" in app.state.market_source.get_tickers()


def test_mock_mode_watchlist_remove_trigger_updates_db_and_source(client, app, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    response = client.post("/api/chat", json={"message": "remove AAPL from the watchlist"})
    assert response.status_code == 200
    body = response.json()
    assert body["watchlist_changes"] == [{"ticker": "AAPL", "action": "remove", "success": True}]
    assert "AAPL" not in db.get_watchlist()
    assert "AAPL" not in app.state.market_source.get_tickers()


def test_mock_mode_watchlist_remove_trigger_not_present_fails_gracefully(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    response = client.post("/api/chat", json={"message": "remove ZZZZ from watchlist"})
    assert response.status_code == 200
    body = response.json()
    assert body["watchlist_changes"][0]["success"] is False
    assert "not on the watchlist" in body["watchlist_changes"][0]["reason"]


def test_mock_mode_persists_user_and_assistant_messages(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    client.post("/api/chat", json={"message": "add PYPL to watchlist"})

    history = db.get_chat_messages()
    assert len(history) == 2
    assert history[0]["role"] == "user"
    assert history[0]["content"] == "add PYPL to watchlist"
    assert history[0]["actions"] is None
    assert history[1]["role"] == "assistant"
    assert history[1]["actions"]["watchlist_changes"][0]["ticker"] == "PYPL"


# --------------------------------------------------------------------------
# Real LLM path (litellm.completion mocked -- no network calls)
# --------------------------------------------------------------------------


def test_real_mode_valid_structured_output(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-tests")
    import app.llm.client as client_module

    content = json.dumps(
        {
            "message": "Your portfolio is well diversified.",
            "trades": [],
            "watchlist_changes": [{"ticker": "PYPL", "action": "add"}],
        }
    )
    monkeypatch.setattr(client_module, "completion", _fake_completion_returning(content))

    response = client.post("/api/chat", json={"message": "How's my portfolio?"})
    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "Your portfolio is well diversified."
    assert body["watchlist_changes"] == [
        {"ticker": "PYPL", "action": "add", "success": True, "already_present": False}
    ]


def test_real_mode_malformed_output_falls_back_gracefully(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-tests")
    import app.llm.client as client_module

    monkeypatch.setattr(client_module, "completion", _fake_completion_returning("not valid json"))

    response = client.post("/api/chat", json={"message": "How's my portfolio?"})
    assert response.status_code == 200
    body = response.json()
    assert body["trades"] == []
    assert body["watchlist_changes"] == []
    assert isinstance(body["message"], str) and len(body["message"]) > 0

    # Still persisted, despite the malformed upstream response.
    history = db.get_chat_messages()
    assert len(history) == 2
    assert history[1]["role"] == "assistant"


def test_real_mode_completion_raising_falls_back_gracefully(client, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-tests")
    import app.llm.client as client_module

    def _raise(**kwargs):
        raise RuntimeError("network is down")

    monkeypatch.setattr(client_module, "completion", _raise)

    response = client.post("/api/chat", json={"message": "How's my portfolio?"})
    assert response.status_code == 200
    body = response.json()
    assert body["trades"] == []
    assert body["watchlist_changes"] == []


def test_real_mode_trade_execution(client, app, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-tests")
    import app.llm.client as client_module

    price = app.state.price_cache.get_price("GOOGL")
    assert price is not None

    content = json.dumps(
        {
            "message": "Buying 3 shares of GOOGL as requested.",
            "trades": [{"ticker": "GOOGL", "side": "buy", "quantity": 3}],
            "watchlist_changes": [],
        }
    )
    monkeypatch.setattr(client_module, "completion", _fake_completion_returning(content))

    response = client.post("/api/chat", json={"message": "buy 3 GOOGL"})
    assert response.status_code == 200
    body = response.json()
    assert body["trades"][0]["success"] is True
    assert body["trades"][0]["price"] == pytest.approx(price)


def test_post_chat_validation_requires_message_field(client, monkeypatch):
    monkeypatch.setenv("LLM_MOCK", "true")
    response = client.post("/api/chat", json={})
    assert response.status_code == 422
