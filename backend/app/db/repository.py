"""Public repository API for the FinAlly database.

This is the *only* place trade-execution rules (PLAN.md §7) are implemented.
The backend API layer and the LLM/chat layer must both call `execute_trade`
rather than re-implementing buy/sell validation or cost-basis math.

All functions default to `user_id="default"` (the single-user model from
PLAN.md §7) but accept an explicit `user_id` so the schema's multi-user
readiness isn't wasted.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal

from ._util import new_id, now_iso
from .connection import get_connection

# Quantities are floats; after a sell, treat anything within this tolerance
# of zero as exactly zero (avoids leaving a position row with a residual
# like 1e-16 shares due to float rounding across a long trade history).
_QUANTITY_EPSILON = 1e-9


@dataclass(frozen=True, slots=True)
class TradeResult:
    """Outcome of a call to `execute_trade`.

    `success=False` means the trade was rejected and nothing was written to
    the database; `reason` explains why. On success, the remaining fields
    describe the post-trade state so callers (API routes, the LLM chat flow)
    can build a response without a second round-trip to the database.
    """

    success: bool
    reason: str | None = None
    ticker: str | None = None
    side: str | None = None
    quantity: float | None = None
    price: float | None = None
    cash_balance: float | None = None
    position_quantity: float | None = None
    avg_cost: float | None = None


# --------------------------------------------------------------------------
# Cash / portfolio
# --------------------------------------------------------------------------


def get_cash_balance(user_id: str = "default") -> float:
    """Return the user's current cash balance.

    Returns 0.0 if no profile row exists for `user_id` (should not happen for
    "default" after lazy init, which always seeds it).
    """
    with get_connection() as conn:
        row = conn.execute(
            "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
        ).fetchone()
        return row["cash_balance"] if row is not None else 0.0


def get_positions(user_id: str = "default") -> list[dict]:
    """Return all positions for `user_id` as dicts with keys:
    ticker, quantity, avg_cost, updated_at. Ordered by ticker.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ticker, quantity, avg_cost, updated_at FROM positions "
            "WHERE user_id = ? ORDER BY ticker",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


def execute_trade(
    ticker: str,
    side: Literal["buy", "sell"],
    quantity: float,
    price: float,
    user_id: str = "default",
) -> TradeResult:
    """Execute a market order and persist it, enforcing PLAN.md §7 rules.

    Buy: rejected with TradeResult(success=False, reason=...) if
    `quantity * price > cash_balance`. On success, cash is debited and
    avg_cost becomes the weighted average of the old and new lots
    (`avg_cost = price` if there was no existing position).

    Sell: rejected if `quantity` exceeds the current position's quantity (no
    shorting). avg_cost is unchanged by sells. Cash is credited. If the
    resulting quantity is (within float tolerance of) zero, the position row
    is deleted rather than left at zero.

    Either way, on success a row is appended to `trades`. The whole trade
    (position upsert/delete + cash update + trade log append) commits as a
    single atomic transaction; any failure rolls back everything.

    Ticker is case-normalized to uppercase. Quantity and price must be
    strictly positive, else the trade is rejected without touching the DB.
    """
    ticker = ticker.upper()

    if side not in ("buy", "sell"):
        return TradeResult(success=False, reason=f"Invalid side: {side!r}. Must be 'buy' or 'sell'.")
    if quantity <= 0:
        return TradeResult(success=False, reason="Quantity must be positive.")
    if price <= 0:
        return TradeResult(success=False, reason="Price must be positive.")

    with get_connection() as conn:
        conn.execute("BEGIN IMMEDIATE")
        try:
            profile = conn.execute(
                "SELECT cash_balance FROM users_profile WHERE id = ?", (user_id,)
            ).fetchone()
            if profile is None:
                conn.execute("ROLLBACK")
                return TradeResult(
                    success=False, reason=f"No user profile found for user_id={user_id!r}."
                )
            cash_balance = profile["cash_balance"]

            position = conn.execute(
                "SELECT quantity, avg_cost FROM positions WHERE user_id = ? AND ticker = ?",
                (user_id, ticker),
            ).fetchone()

            now = now_iso()

            if side == "buy":
                cost = quantity * price
                if cost > cash_balance:
                    conn.execute("ROLLBACK")
                    return TradeResult(
                        success=False, reason="Insufficient cash balance for this trade."
                    )
                new_cash = cash_balance - cost
                if position is None:
                    new_qty = quantity
                    new_avg_cost = price
                    conn.execute(
                        "INSERT INTO positions (id, user_id, ticker, quantity, avg_cost, updated_at) "
                        "VALUES (?, ?, ?, ?, ?, ?)",
                        (new_id(), user_id, ticker, new_qty, new_avg_cost, now),
                    )
                else:
                    old_qty = position["quantity"]
                    old_avg_cost = position["avg_cost"]
                    new_qty = old_qty + quantity
                    new_avg_cost = (old_avg_cost * old_qty + price * quantity) / new_qty
                    conn.execute(
                        "UPDATE positions SET quantity = ?, avg_cost = ?, updated_at = ? "
                        "WHERE user_id = ? AND ticker = ?",
                        (new_qty, new_avg_cost, now, user_id, ticker),
                    )
            else:  # side == "sell"
                if position is None or quantity > position["quantity"] + _QUANTITY_EPSILON:
                    conn.execute("ROLLBACK")
                    return TradeResult(
                        success=False, reason="Cannot sell more shares than currently held."
                    )
                old_qty = position["quantity"]
                new_avg_cost = position["avg_cost"]
                new_qty = old_qty - quantity
                new_cash = cash_balance + quantity * price
                if abs(new_qty) < _QUANTITY_EPSILON:
                    new_qty = 0.0
                    conn.execute(
                        "DELETE FROM positions WHERE user_id = ? AND ticker = ?",
                        (user_id, ticker),
                    )
                else:
                    conn.execute(
                        "UPDATE positions SET quantity = ?, updated_at = ? "
                        "WHERE user_id = ? AND ticker = ?",
                        (new_qty, now, user_id, ticker),
                    )

            conn.execute(
                "UPDATE users_profile SET cash_balance = ? WHERE id = ?",
                (new_cash, user_id),
            )
            conn.execute(
                "INSERT INTO trades (id, user_id, ticker, side, quantity, price, executed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (new_id(), user_id, ticker, side, quantity, price, now),
            )
            conn.execute("COMMIT")

            return TradeResult(
                success=True,
                ticker=ticker,
                side=side,
                quantity=quantity,
                price=price,
                cash_balance=new_cash,
                position_quantity=new_qty,
                avg_cost=new_avg_cost if new_qty > 0 else None,
            )
        except Exception:
            conn.execute("ROLLBACK")
            raise


# --------------------------------------------------------------------------
# Watchlist
# --------------------------------------------------------------------------


def get_watchlist(user_id: str = "default") -> list[str]:
    """Return the user's watchlist tickers, ordered by when they were added."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT ticker FROM watchlist WHERE user_id = ? ORDER BY added_at, rowid",
            (user_id,),
        ).fetchall()
        return [row["ticker"] for row in rows]


def add_to_watchlist(ticker: str, user_id: str = "default") -> bool:
    """Add `ticker` to the user's watchlist.

    Idempotent no-op behavior: if the ticker is already on the watchlist,
    returns False and does not insert a duplicate row (rather than raising
    on the UNIQUE(user_id, ticker) constraint). Returns True if a new row
    was inserted. Ticker is case-normalized to uppercase.
    """
    ticker = ticker.upper()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT 1 FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        ).fetchone()
        if existing is not None:
            return False
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (new_id(), user_id, ticker, now_iso()),
        )
        conn.commit()
        return True


def remove_from_watchlist(ticker: str, user_id: str = "default") -> bool:
    """Remove `ticker` from the user's watchlist.

    Returns True if a row was deleted, False if the ticker wasn't present.
    """
    ticker = ticker.upper()
    with get_connection() as conn:
        cursor = conn.execute(
            "DELETE FROM watchlist WHERE user_id = ? AND ticker = ?", (user_id, ticker)
        )
        conn.commit()
        return cursor.rowcount > 0


# --------------------------------------------------------------------------
# Portfolio snapshots
# --------------------------------------------------------------------------


def record_snapshot(total_value: float, user_id: str = "default") -> None:
    """Append a portfolio value snapshot with the current timestamp."""
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO portfolio_snapshots (id, user_id, total_value, recorded_at) "
            "VALUES (?, ?, ?, ?)",
            (new_id(), user_id, total_value, now_iso()),
        )
        conn.commit()


def get_snapshot_history(user_id: str = "default") -> list[dict]:
    """Return all snapshots for `user_id` as dicts with keys total_value,
    recorded_at, ordered oldest-first.
    """
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT total_value, recorded_at FROM portfolio_snapshots "
            "WHERE user_id = ? ORDER BY recorded_at, rowid",
            (user_id,),
        ).fetchall()
        return [dict(row) for row in rows]


# --------------------------------------------------------------------------
# Chat messages
# --------------------------------------------------------------------------


def get_chat_messages(limit: int = 20, user_id: str = "default") -> list[dict]:
    """Return the most recent `limit` chat messages for `user_id`, oldest-first.

    Each dict has keys: role, content, actions (parsed JSON dict, or None),
    created_at.
    """
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content, actions, created_at FROM (
                SELECT role, content, actions, created_at, rowid
                FROM chat_messages
                WHERE user_id = ?
                ORDER BY created_at DESC, rowid DESC
                LIMIT ?
            )
            ORDER BY created_at ASC, rowid ASC
            """,
            (user_id, limit),
        ).fetchall()
        result = []
        for row in rows:
            actions = json.loads(row["actions"]) if row["actions"] is not None else None
            result.append(
                {
                    "role": row["role"],
                    "content": row["content"],
                    "actions": actions,
                    "created_at": row["created_at"],
                }
            )
        return result


def append_chat_message(
    role: str,
    content: str,
    actions: dict | None = None,
    user_id: str = "default",
) -> None:
    """Append a chat message. `actions` is JSON-encoded if provided, else
    stored as NULL. `role` should be "user" or "assistant" per the schema's
    CHECK constraint.
    """
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, user_id, role, content, actions, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (
                new_id(),
                user_id,
                role,
                content,
                json.dumps(actions) if actions is not None else None,
                now_iso(),
            ),
        )
        conn.commit()
