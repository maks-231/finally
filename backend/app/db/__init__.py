"""FinAlly database package: schema, lazy-init connection management, and the
repository API that the rest of the backend (REST routes, LLM chat flow)
should use for all persistence. See PLAN.md §7 for the schema contract.
"""

from __future__ import annotations

from .connection import get_connection, get_db_path, init_db
from .repository import (
    TradeResult,
    add_to_watchlist,
    append_chat_message,
    execute_trade,
    get_cash_balance,
    get_chat_messages,
    get_positions,
    get_snapshot_history,
    get_watchlist,
    record_snapshot,
    remove_from_watchlist,
)

__all__ = [
    "get_connection",
    "get_db_path",
    "init_db",
    "TradeResult",
    "add_to_watchlist",
    "append_chat_message",
    "execute_trade",
    "get_cash_balance",
    "get_chat_messages",
    "get_positions",
    "get_snapshot_history",
    "get_watchlist",
    "record_snapshot",
    "remove_from_watchlist",
]
