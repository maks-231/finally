"use client";

import { FormEvent, useState } from "react";
import { TradeSide } from "@/lib/types";

interface TradeBarProps {
  defaultTicker?: string | null;
  onTrade: (ticker: string, quantity: number, side: TradeSide) => Promise<boolean>;
  pending: boolean;
  error: string | null;
}

export function TradeBar({ defaultTicker, onTrade, pending, error }: TradeBarProps) {
  const [ticker, setTicker] = useState(defaultTicker ?? "");
  const [quantity, setQuantity] = useState("");

  async function submit(side: TradeSide, e: FormEvent) {
    e.preventDefault();
    const qty = parseFloat(quantity);
    if (!ticker.trim() || !Number.isFinite(qty) || qty <= 0) return;
    const ok = await onTrade(ticker.trim().toUpperCase(), qty, side);
    if (ok) setQuantity("");
  }

  return (
    <section className="rounded border border-border-muted bg-bg-panel p-3">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">Trade</h2>
      <form className="flex flex-wrap items-end gap-2" data-testid="trade-bar">
        <div className="flex flex-col gap-1">
          <label htmlFor="trade-ticker" className="text-[10px] uppercase text-text-muted">
            Ticker
          </label>
          <input
            id="trade-ticker"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="AAPL"
            className="w-24 rounded border border-border-muted bg-bg-base px-2 py-1.5 font-mono text-sm uppercase text-text-primary outline-none focus:border-blue-primary"
            data-testid="trade-ticker-input"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor="trade-quantity" className="text-[10px] uppercase text-text-muted">
            Quantity
          </label>
          <input
            id="trade-quantity"
            type="number"
            step="any"
            min="0"
            inputMode="decimal"
            value={quantity}
            onChange={(e) => setQuantity(e.target.value)}
            placeholder="0.00"
            className="w-28 rounded border border-border-muted bg-bg-base px-2 py-1.5 font-mono text-sm text-text-primary outline-none focus:border-blue-primary"
            data-testid="trade-quantity-input"
          />
        </div>
        <button
          type="submit"
          disabled={pending}
          onClick={(e) => submit("buy", e)}
          className="rounded bg-purple-secondary px-4 py-1.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          data-testid="trade-buy-button"
        >
          Buy
        </button>
        <button
          type="submit"
          disabled={pending}
          onClick={(e) => submit("sell", e)}
          className="rounded border border-down px-4 py-1.5 text-sm font-semibold text-down hover:bg-down/10 disabled:opacity-50"
          data-testid="trade-sell-button"
        >
          Sell
        </button>
        {pending && <span className="text-xs text-text-muted">Submitting…</span>}
      </form>
      {error && (
        <p className="mt-2 text-xs text-down" data-testid="trade-error">
          {error}
        </p>
      )}
    </section>
  );
}
