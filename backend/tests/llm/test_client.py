"""Tests for app.llm.client (litellm.completion mocked -- no real network
calls, per the task's testing requirement).
"""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

import app.llm.client as client_module
from app.llm.client import LLMError, get_chat_response


def _fake_completion_returning(content: str):
    def _fake_completion(**kwargs):
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    return _fake_completion


def test_get_chat_response_parses_valid_structured_output(monkeypatch):
    content = json.dumps(
        {
            "message": "Here's your analysis.",
            "trades": [{"ticker": "AAPL", "side": "buy", "quantity": 1}],
            "watchlist_changes": [],
        }
    )
    monkeypatch.setattr(client_module, "completion", _fake_completion_returning(content))

    result = get_chat_response([{"role": "user", "content": "hi"}])
    assert result.message == "Here's your analysis."
    assert result.trades[0].ticker == "AAPL"


def test_get_chat_response_raises_llm_error_on_malformed_json(monkeypatch):
    monkeypatch.setattr(client_module, "completion", _fake_completion_returning("not json"))

    with pytest.raises(LLMError):
        get_chat_response([{"role": "user", "content": "hi"}])


def test_get_chat_response_raises_llm_error_on_schema_mismatch(monkeypatch):
    # Valid JSON, but missing the required `message` field.
    content = json.dumps({"trades": []})
    monkeypatch.setattr(client_module, "completion", _fake_completion_returning(content))

    with pytest.raises(LLMError):
        get_chat_response([{"role": "user", "content": "hi"}])


def test_get_chat_response_raises_llm_error_when_completion_raises(monkeypatch):
    def _raise(**kwargs):
        raise ConnectionError("network unreachable")

    monkeypatch.setattr(client_module, "completion", _raise)

    with pytest.raises(LLMError):
        get_chat_response([{"role": "user", "content": "hi"}])


def test_get_chat_response_passes_model_and_extra_body(monkeypatch):
    captured = {}

    def _capture(**kwargs):
        captured.update(kwargs)
        content = json.dumps({"message": "ok", "trades": [], "watchlist_changes": []})
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
        )

    monkeypatch.setattr(client_module, "completion", _capture)
    get_chat_response([{"role": "user", "content": "hi"}])

    assert captured["model"] == "openrouter/openai/gpt-oss-120b"
    assert captured["extra_body"] == {"provider": {"order": ["cerebras"]}}
    assert captured["response_format"] is not None
