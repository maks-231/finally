// Thin fetch wrapper for the FinAlly REST API (PLAN.md §8).
//
// All calls are same-origin ("/api/*") in production, served by FastAPI.
// In local dev, next.config.ts rewrites /api/* to http://localhost:8000.

import {
  ApiError,
  ChatMessageRecord,
  ChatResponse,
  PortfolioSnapshot,
  PortfolioSummary,
  TradeRequest,
  WatchlistItem,
} from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError("Network error — could not reach the server.", 0);
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      detail = body?.detail ?? body?.error ?? body?.message ?? detail;
    } catch {
      // response body wasn't JSON; fall back to default message
    }
    throw new ApiError(detail, res.status);
  }

  if (res.status === 204) {
    return undefined as T;
  }

  try {
    return (await res.json()) as T;
  } catch {
    return undefined as T;
  }
}

export function getPortfolio(): Promise<PortfolioSummary> {
  return request<PortfolioSummary>("/api/portfolio");
}

export function postTrade(trade: TradeRequest): Promise<unknown> {
  return request("/api/portfolio/trade", {
    method: "POST",
    body: JSON.stringify(trade),
  });
}

export function getPortfolioHistory(): Promise<PortfolioSnapshot[]> {
  return request<PortfolioSnapshot[]>("/api/portfolio/history");
}

/** Normalizes watchlist responses whether the backend returns an array of
 * objects, an array of ticker strings, or a wrapper object. */
function normalizeWatchlist(raw: unknown): WatchlistItem[] {
  const arr: unknown[] = Array.isArray(raw)
    ? raw
    : Array.isArray((raw as { watchlist?: unknown[] })?.watchlist)
      ? (raw as { watchlist: unknown[] }).watchlist
      : Array.isArray((raw as { tickers?: unknown[] })?.tickers)
        ? (raw as { tickers: unknown[] }).tickers
        : [];

  return arr.map((item) =>
    typeof item === "string"
      ? { ticker: item }
      : (item as WatchlistItem),
  );
}

export async function getWatchlist(): Promise<WatchlistItem[]> {
  const raw = await request<unknown>("/api/watchlist");
  return normalizeWatchlist(raw);
}

export function addWatchlistTicker(ticker: string): Promise<unknown> {
  return request("/api/watchlist", {
    method: "POST",
    body: JSON.stringify({ ticker }),
  });
}

export function removeWatchlistTicker(ticker: string): Promise<unknown> {
  return request(`/api/watchlist/${encodeURIComponent(ticker)}`, {
    method: "DELETE",
  });
}

function normalizeChatHistory(raw: unknown): ChatMessageRecord[] {
  const arr: unknown[] = Array.isArray(raw)
    ? raw
    : Array.isArray((raw as { messages?: unknown[] })?.messages)
      ? (raw as { messages: unknown[] }).messages
      : [];
  return arr as ChatMessageRecord[];
}

export async function getChatHistory(): Promise<ChatMessageRecord[]> {
  const raw = await request<unknown>("/api/chat");
  return normalizeChatHistory(raw);
}

export function postChatMessage(message: string): Promise<ChatResponse> {
  return request<ChatResponse>("/api/chat", {
    method: "POST",
    body: JSON.stringify({ message }),
  });
}
