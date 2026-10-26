"""Trade execution tests: weighted-average cost basis, cash rules, no shorting."""

from __future__ import annotations

import pytest


def test_buy_with_no_existing_position_sets_avg_cost_to_price(db):
    result = db.execute_trade(ticker="aapl", side="buy", quantity=10, price=100.0)

    assert result.success is True
    assert result.ticker == "AAPL"  # normalized to uppercase
    assert result.position_quantity == 10
    assert result.avg_cost == 100.0
    assert result.cash_balance == pytest.approx(10000.0 - 1000.0)
    assert db.get_cash_balance() == pytest.approx(9000.0)

    positions = db.get_positions()
    assert len(positions) == 1
    assert positions[0]["ticker"] == "AAPL"
    assert positions[0]["quantity"] == 10
    assert positions[0]["avg_cost"] == 100.0


def test_weighted_average_cost_across_multiple_buys(db):
    db.execute_trade(ticker="AAPL", side="buy", quantity=10, price=100.0)
    result = db.execute_trade(ticker="AAPL", side="buy", quantity=10, price=200.0)

    # (100*10 + 200*10) / 20 = 150
    assert result.success is True
    assert result.position_quantity == 20
    assert result.avg_cost == pytest.approx(150.0)

    result3 = db.execute_trade(ticker="AAPL", side="buy", quantity=5, price=50.0)
    # (150*20 + 50*5) / 25 = (3000+250)/25 = 130
    assert result3.avg_cost == pytest.approx(130.0)
    assert result3.position_quantity == 25


def test_buy_rejected_when_insufficient_cash(db):
    result = db.execute_trade(ticker="AAPL", side="buy", quantity=1000, price=100.0)

    assert result.success is False
    assert result.reason is not None
    assert "cash" in result.reason.lower()
    # Nothing should have been written.
    assert db.get_cash_balance() == 10000.0
    assert db.get_positions() == []


def test_buy_exact_cash_amount_succeeds(db):
    # quantity * price == cash_balance exactly should NOT be rejected
    # (rule is "rejected if cost > cash_balance", strictly greater-than).
    result = db.execute_trade(ticker="AAPL", side="buy", quantity=100, price=100.0)
    assert result.success is True
    assert db.get_cash_balance() == pytest.approx(0.0)


def test_sell_rejected_when_exceeding_position_no_shorting(db):
    db.execute_trade(ticker="AAPL", side="buy", quantity=10, price=100.0)
    result = db.execute_trade(ticker="AAPL", side="sell", quantity=11, price=100.0)

    assert result.success is False
    assert "sell" in result.reason.lower() or "held" in result.reason.lower()
    positions = db.get_positions()
    assert positions[0]["quantity"] == 10  # unchanged


def test_sell_rejected_with_no_existing_position(db):
    result = db.execute_trade(ticker="AAPL", side="sell", quantity=1, price=100.0)
    assert result.success is False


def test_sell_partial_leaves_avg_cost_unchanged(db):
    db.execute_trade(ticker="AAPL", side="buy", quantity=10, price=100.0)
    result = db.execute_trade(ticker="AAPL", side="sell", quantity=4, price=150.0)

    assert result.success is True
    assert result.position_quantity == 6
    assert result.avg_cost == pytest.approx(100.0)  # unchanged by sell
    assert result.cash_balance == pytest.approx(10000.0 - 1000.0 + 600.0)

    positions = db.get_positions()
    assert positions[0]["quantity"] == 6
    assert positions[0]["avg_cost"] == pytest.approx(100.0)


def test_sell_full_position_deletes_row(db):
    db.execute_trade(ticker="AAPL", side="buy", quantity=10, price=100.0)
    result = db.execute_trade(ticker="AAPL", side="sell", quantity=10, price=120.0)

    assert result.success is True
    assert result.position_quantity == 0
    assert result.avg_cost is None
    assert db.get_positions() == []
    assert db.get_cash_balance() == pytest.approx(10000.0 - 1000.0 + 1200.0)


def test_trade_log_records_both_buy_and_sell(db):
    db.execute_trade(ticker="AAPL", side="buy", quantity=10, price=100.0)
    db.execute_trade(ticker="AAPL", side="sell", quantity=5, price=110.0)

    import sqlite3

    with db.get_connection() as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT side, quantity, price FROM trades ORDER BY executed_at, rowid"
        ).fetchall()

    assert len(rows) == 2
    assert rows[0]["side"] == "buy"
    assert rows[0]["quantity"] == 10
    assert rows[1]["side"] == "sell"
    assert rows[1]["quantity"] == 5


def test_invalid_side_rejected(db):
    result = db.execute_trade(ticker="AAPL", side="hold", quantity=1, price=100.0)  # type: ignore[arg-type]
    assert result.success is False


@pytest.mark.parametrize("bad_quantity", [0, -5])
def test_non_positive_quantity_rejected(db, bad_quantity):
    result = db.execute_trade(ticker="AAPL", side="buy", quantity=bad_quantity, price=100.0)
    assert result.success is False


@pytest.mark.parametrize("bad_price", [0, -10])
def test_non_positive_price_rejected(db, bad_price):
    result = db.execute_trade(ticker="AAPL", side="buy", quantity=1, price=bad_price)
    assert result.success is False


def test_independent_positions_per_ticker(db):
    db.execute_trade(ticker="AAPL", side="buy", quantity=10, price=100.0)
    db.execute_trade(ticker="MSFT", side="buy", quantity=5, price=200.0)

    positions = {p["ticker"]: p for p in db.get_positions()}
    assert positions["AAPL"]["quantity"] == 10
    assert positions["MSFT"]["quantity"] == 5
