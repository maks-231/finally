"use client";

import { useEffect, useRef, useState } from "react";
import { ConnectionState, PriceMap, PricePoint, PriceUpdate } from "@/lib/types";

const MAX_HISTORY_POINTS = 300;

interface UsePriceStreamResult {
  prices: PriceMap;
  history: Record<string, PricePoint[]>;
  connectionState: ConnectionState;
}

/**
 * Subscribes to GET /api/stream/prices via native EventSource.
 *
 * - Surfaces connection state (connected/reconnecting/disconnected) derived
 *   from EventSource's readyState + onopen/onerror, for the header's status dot.
 * - Accumulates per-ticker price history client-side, starting empty on every
 *   mount (no backfill) — used to progressively build sparklines/main chart.
 */
export function usePriceStream(url = "/api/stream/prices"): UsePriceStreamResult {
  const [prices, setPrices] = useState<PriceMap>({});
  const [history, setHistory] = useState<Record<string, PricePoint[]>>({});
  const [connectionState, setConnectionState] = useState<ConnectionState>("disconnected");
  const hasConnectedOnce = useRef(false);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.EventSource === "undefined") {
      return;
    }

    const source = new EventSource(url);

    source.onopen = () => {
      hasConnectedOnce.current = true;
      setConnectionState("connected");
    };

    source.onerror = () => {
      // EventSource auto-reconnects. If we've connected before, this is a
      // reconnect attempt (yellow); readyState CLOSED with no prior
      // connection means it never managed to connect (red).
      if (source.readyState === EventSource.CLOSED) {
        setConnectionState(hasConnectedOnce.current ? "reconnecting" : "disconnected");
      } else {
        setConnectionState("reconnecting");
      }
    };

    source.onmessage = (event: MessageEvent<string>) => {
      try {
        const payload = JSON.parse(event.data) as Record<string, PriceUpdate>;
        setPrices((prev) => ({ ...prev, ...payload }));
        setHistory((prev) => {
          const next = { ...prev };
          for (const [ticker, update] of Object.entries(payload)) {
            const existing = next[ticker] ?? [];
            const point: PricePoint = { timestamp: update.timestamp, price: update.price };
            next[ticker] = [...existing, point].slice(-MAX_HISTORY_POINTS);
          }
          return next;
        });
      } catch {
        // Ignore malformed events; the stream will keep sending valid ones.
      }
    };

    return () => {
      source.close();
    };
  }, [url]);

  return { prices, history, connectionState };
}
