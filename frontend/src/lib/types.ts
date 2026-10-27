// Shared types for the FinAlly frontend.
//
// These mirror the contracts described in planning/PLAN.md §8. Where the
// real backend (built in parallel by the backend-api-engineer agent) differs,
// the API layer in `lib/api.ts` normalizes responses defensively so the UI
// doesn't break on small shape differences.

export type TradeSide = "buy" | "sell";
export type PriceDirection = "up" | "down" | "flat";

/** A single ticker price update, as pushed by GET /api/stream/prices (SSE). */
export interface PriceUpdate {
  ticker: string;
  price: number;
  previous_price: number;
  timestamp: number;
  change: number;
  change_percent?: number;
  direction: PriceDirection;
}

/** Map of ticker -> latest PriceUpdate, as received per SSE event. */
export type PriceMap = Record<string, PriceUpdate>;

export type ConnectionState = "connected" | "reconnecting" | "disconnected";

/** One point accumulated client-side for a ticker's sparkline / main chart. */
export interface PricePoint {
  timestamp: number;
  price: number;
}

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  unrealized_pnl: number;
  unrealized_pnl_percent: number;
}

export interface PortfolioSummary {
  cash_balance: number;
  positions: Position[];
  total_value: number;
}

export interface PortfolioSnapshot {
  total_value: number;
  recorded_at: string;
}

export interface WatchlistItem {
  ticker: string;
  price?: number;
  change_percent?: number;
}

export interface TradeRequest {
  ticker: string;
  quantity: number;
  side: TradeSide;
}

export interface ExecutedTrade {
  ticker: string;
  side: TradeSide;
  quantity: number;
  price?: number;
  success?: boolean;
  reason?: string;
}

export interface WatchlistChange {
  ticker: string;
  action: "add" | "remove";
  success?: boolean;
  reason?: string;
}

export interface ChatMessageRecord {
  id?: string;
  role: "user" | "assistant";
  content: string;
  actions?: {
    trades?: ExecutedTrade[];
    watchlist_changes?: WatchlistChange[];
  } | null;
  created_at?: string;
}

export interface ChatResponse {
  message: string;
  trades?: ExecutedTrade[];
  watchlist_changes?: WatchlistChange[];
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
    this.name = "ApiError";
  }
}
