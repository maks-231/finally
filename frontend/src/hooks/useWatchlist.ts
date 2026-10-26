"use client";

import { useCallback, useEffect, useState } from "react";
import { addWatchlistTicker, getWatchlist, removeWatchlistTicker } from "@/lib/api";
import { ApiError, WatchlistItem } from "@/lib/types";

export function useWatchlist() {
  const [watchlist, setWatchlist] = useState<WatchlistItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refetch = useCallback(async () => {
    try {
      const data = await getWatchlist();
      setWatchlist(data);
      setError(null);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load watchlist.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch-on-mount: no server-rendered initial data in this static export.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refetch();
  }, [refetch]);

  const add = useCallback(
    async (ticker: string) => {
      const normalized = ticker.trim().toUpperCase();
      if (!normalized) return false;
      try {
        await addWatchlistTicker(normalized);
        await refetch();
        setError(null);
        return true;
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to add ticker.");
        return false;
      }
    },
    [refetch],
  );

  const remove = useCallback(
    async (ticker: string) => {
      try {
        await removeWatchlistTicker(ticker);
        await refetch();
        setError(null);
        return true;
      } catch (err) {
        setError(err instanceof ApiError ? err.message : "Failed to remove ticker.");
        return false;
      }
    },
    [refetch],
  );

  return { watchlist, loading, error, add, remove, refetch };
}
