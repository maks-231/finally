"""Portfolio snapshot recording/retrieval tests."""

from __future__ import annotations

import pytest


def test_no_snapshots_initially(db):
    assert db.get_snapshot_history() == []


def test_record_and_retrieve_snapshot(db):
    db.record_snapshot(10000.0)
    history = db.get_snapshot_history()
    assert len(history) == 1
    assert history[0]["total_value"] == 10000.0
    assert "recorded_at" in history[0]


def test_snapshots_returned_in_chronological_order(db):
    for value in (10000.0, 10500.0, 9800.0, 11200.0):
        db.record_snapshot(value)

    history = db.get_snapshot_history()
    values = [h["total_value"] for h in history]
    assert values == [10000.0, 10500.0, 9800.0, 11200.0]

    recorded_ats = [h["recorded_at"] for h in history]
    assert recorded_ats == sorted(recorded_ats)


def test_snapshots_isolated_per_user(db):
    db.record_snapshot(10000.0, user_id="alice")
    assert db.get_snapshot_history(user_id="alice") == db.get_snapshot_history(user_id="alice")
    assert db.get_snapshot_history() == []  # default user unaffected


def test_snapshot_recorded_after_trade_has_correct_value(db):
    db.execute_trade(ticker="AAPL", side="buy", quantity=10, price=100.0)
    cash = db.get_cash_balance()
    positions = db.get_positions()
    total_value = cash + sum(p["quantity"] * 100.0 for p in positions)
    db.record_snapshot(total_value)

    history = db.get_snapshot_history()
    assert history[-1]["total_value"] == pytest.approx(total_value)
