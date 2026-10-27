"use client";

import { useCallback, useEffect, useState } from "react";
import { getPortfolioHistory } from "@/lib/api";
import { PortfolioSnapshot } from "@/lib/types";

const POLL_INTERVAL_MS = 30000;

export function usePortfolioHistory() {
  const [history, setHistory] = useState<PortfolioSnapshot[]>([]);
  const [loading, setLoading] = useState(true);

  const refetch = useCallback(async () => {
    try {
      const data = await getPortfolioHistory();
      setHistory(data);
    } catch {
      // Non-critical for the rest of the UI; chart just stays empty.
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount + poll: no server-rendered initial data in this static
    // export, so an effect is the correct place to kick off the first fetch.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refetch();
    const interval = setInterval(refetch, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [refetch]);

  return { history, loading, refetch };
}
