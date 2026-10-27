"use client";

import { FormEvent, useState } from "react";
import { PriceMap, PricePoint } from "@/lib/types";
import { WatchlistRow } from "./WatchlistRow";

interface WatchlistPanelProps {
  tickers: string[];
  prices: PriceMap;
  history: Record<string, PricePoint[]>;
  selectedTicker: string | null;
  onSelect: (ticker: string) => void;
  onAdd: (ticker: string) => Promise<boolean>;
  onRemove: (ticker: string) => void;
  error: string | null;
}

export function WatchlistPanel({
  tickers,
  prices,
  history,
  selectedTicker,
  onSelect,
  onAdd,
  onRemove,
  error,
}: WatchlistPanelProps) {
  const [input, setInput] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!input.trim()) return;
    const ok = await onAdd(input);
    if (ok) setInput("");
  }

  return (
    <section className="flex h-full flex-col rounded border border-border-muted bg-bg-panel">
      <div className="flex items-center justify-between border-b border-border-muted px-3 py-2">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-text-muted">Watchlist</h2>
        <form onSubmit={handleSubmit} className="flex items-center gap-1">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value.toUpperCase())}
            placeholder="TICKER"
            className="w-20 rounded border border-border-muted bg-bg-base px-2 py-1 text-xs font-mono uppercase text-text-primary outline-none focus:border-blue-primary"
            aria-label="Add ticker to watchlist"
            data-testid="watchlist-add-input"
          />
          <button
            type="submit"
            className="rounded bg-blue-primary px-2 py-1 text-xs font-semibold text-white hover:opacity-90"
            data-testid="watchlist-add-button"
          >
            Add
          </button>
        </form>
      </div>
      {error && (
        <div className="px-3 py-1 text-xs text-down" data-testid="watchlist-error">
          {error}
        </div>
      )}
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wide text-text-muted">
              <th className="px-3 py-1.5">Ticker</th>
              <th className="px-3 py-1.5">Price</th>
              <th className="px-3 py-1.5">Chg%</th>
              <th className="px-3 py-1.5">Trend</th>
              <th className="px-2 py-1.5" />
            </tr>
          </thead>
          <tbody>
            {tickers.map((ticker) => (
              <WatchlistRow
                key={ticker}
                ticker={ticker}
                priceUpdate={prices[ticker]}
                history={history[ticker] ?? []}
                selected={ticker === selectedTicker}
                onSelect={onSelect}
                onRemove={onRemove}
              />
            ))}
            {tickers.length === 0 && (
              <tr>
                <td colSpan={5} className="px-3 py-6 text-center text-xs text-text-muted">
                  Watchlist is empty. Add a ticker above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
