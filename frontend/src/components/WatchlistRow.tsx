"use client";

import { useEffect, useRef, useState } from "react";
import { PricePoint, PriceUpdate } from "@/lib/types";
import { formatCurrency, formatPercent } from "@/lib/format";
import { Sparkline } from "./Sparkline";

interface WatchlistRowProps {
  ticker: string;
  priceUpdate?: PriceUpdate;
  history: PricePoint[];
  selected: boolean;
  onSelect: (ticker: string) => void;
  onRemove: (ticker: string) => void;
}

export function WatchlistRow({
  ticker,
  priceUpdate,
  history,
  selected,
  onSelect,
  onRemove,
}: WatchlistRowProps) {
  const [flashClass, setFlashClass] = useState("");
  const [flashNonce, setFlashNonce] = useState(0);
  const lastTimestamp = useRef<number | null>(null);

  useEffect(() => {
    if (!priceUpdate) return;
    const isNewTick = lastTimestamp.current !== null && priceUpdate.timestamp !== lastTimestamp.current;
    if (isNewTick && priceUpdate.direction !== "flat") {
      setFlashClass(priceUpdate.direction === "up" ? "price-flash-up" : "price-flash-down");
      setFlashNonce((n) => n + 1);
    }
    lastTimestamp.current = priceUpdate.timestamp;
  }, [priceUpdate]);

  const changePercent = priceUpdate?.change_percent ?? 0;
  const isPositive = changePercent >= 0;

  return (
    <tr
      className={`cursor-pointer border-b border-border-subtle text-sm transition-colors hover:bg-bg-panel-raised ${
        selected ? "bg-bg-panel-raised" : ""
      }`}
      onClick={() => onSelect(ticker)}
      data-testid={`watchlist-row-${ticker}`}
    >
      <td className="px-3 py-2 font-mono font-semibold text-text-primary">{ticker}</td>
      <td className="px-3 py-2 font-mono" data-testid={`price-cell-${ticker}`}>
        <span
          key={flashNonce}
          className={`inline-block rounded px-1.5 py-0.5 ${flashClass}`}
          data-testid={`price-flash-${ticker}`}
        >
          {priceUpdate ? formatCurrency(priceUpdate.price) : "—"}
        </span>
      </td>
      <td
        className={`px-3 py-2 font-mono text-xs ${isPositive ? "text-up" : "text-down"}`}
        data-testid={`change-cell-${ticker}`}
      >
        {priceUpdate ? formatPercent(changePercent) : "—"}
      </td>
      <td className="px-3 py-2">
        <Sparkline points={history} positive={isPositive} />
      </td>
      <td className="px-2 py-2 text-right">
        <button
          type="button"
          onClick={(e) => {
            e.stopPropagation();
            onRemove(ticker);
          }}
          className="rounded px-2 py-0.5 text-xs text-text-muted hover:bg-down/20 hover:text-down"
          aria-label={`Remove ${ticker} from watchlist`}
          data-testid={`remove-${ticker}`}
        >
          ✕
        </button>
      </td>
    </tr>
  );
}
