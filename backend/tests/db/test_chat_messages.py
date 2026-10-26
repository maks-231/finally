"""Chat message append/ordering/limit tests."""

from __future__ import annotations


def test_no_messages_initially(db):
    assert db.get_chat_messages() == []


def test_append_and_retrieve_message(db):
    db.append_chat_message(role="user", content="Hello")
    messages = db.get_chat_messages()
    assert len(messages) == 1
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "Hello"
    assert messages[0]["actions"] is None
    assert "created_at" in messages[0]


def test_append_with_actions_roundtrips_json(db):
    actions = {"trades": [{"ticker": "AAPL", "side": "buy", "quantity": 10}]}
    db.append_chat_message(role="assistant", content="Bought it.", actions=actions)
    messages = db.get_chat_messages()
    assert messages[0]["actions"] == actions


def test_messages_returned_oldest_first(db):
    db.append_chat_message(role="user", content="first")
    db.append_chat_message(role="assistant", content="second")
    db.append_chat_message(role="user", content="third")

    messages = db.get_chat_messages()
    assert [m["content"] for m in messages] == ["first", "second", "third"]


def test_limit_returns_most_recent_n_oldest_first(db):
    for i in range(25):
        db.append_chat_message(role="user", content=f"msg-{i}")

    messages = db.get_chat_messages(limit=20)
    assert len(messages) == 20
    # Should be the most recent 20 (msg-5..msg-24), oldest-first.
    assert [m["content"] for m in messages] == [f"msg-{i}" for i in range(5, 25)]


def test_messages_isolated_per_user(db):
    db.append_chat_message(role="user", content="hi", user_id="alice")
    assert len(db.get_chat_messages(user_id="alice")) == 1
    assert db.get_chat_messages() == []  # default user unaffected
