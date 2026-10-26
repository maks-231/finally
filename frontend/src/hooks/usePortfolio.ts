"use client";

import { useCallback, useEffect, useState } from "react";
import { getPortfolio, postTrade } from "@/lib/api";
import { ApiError, PortfolioSummary, TradeSide } from "@/lib/types";

const POLL_INTERVAL_MS = 15000;

export function usePortfolio() {
  const [portfolio, setPortfolio] = useState<PortfolioSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tradeError, setTradeError] = useState<string | null>(null);
  const [tradePending, setTradePending] = useState(false);

  const refetch = useCallback(async () => {
    try {
      const data = await getPortfolio();
      setPortfolio(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load portfolio.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount + poll: this hook has no server-rendered initial data
    // (it's a static export talking to a runtime-only API), so an effect is
    // the correct place to kick off the first fetch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refetch();
    const interval = setInterval(refetch, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refetch]);

  const trade = useCallback(
    async (ticker: string, quantity: number, side: TradeSide) => {
      setTradePending(true);
      setTradeError(null);
      try {
        await postTrade({ ticker, quantity, side });
        await refetch();
        return true;
      } catch (err) {
        setTradeError(err instanceof ApiError ? err.message : "Trade failed.");
        return false;
      } finally {
        setTradePending(false);
      }
    },
    [refetch],
  );

  return { portfolio, loading, error, refetch, trade, tradeError, tradePending, setTradeError };
}
