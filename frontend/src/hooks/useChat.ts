"use client";

import { useCallback, useEffect, useState } from "react";
import { getChatHistory, postChatMessage } from "@/lib/api";
import { ApiError, ChatMessageRecord, ChatResponse } from "@/lib/types";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessageRecord[]>([]);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const data = await getChatHistory();
        setMessages(data);
      } catch {
        // No persisted history yet, or chat unavailable — start with an
        // empty conversation rather than blocking the panel.
      } finally {
        setLoadingHistory(false);
      }
    })();
  }, []);

  const send = useCallback(async (message: string): Promise<ChatResponse | null> => {
    const trimmed = message.trim();
    if (!trimmed) return null;

    setMessages((prev) => [...prev, { role: "user", content: trimmed }]);
    setSending(true);
    setError(null);

    try {
      const response = await postChatMessage(trimmed);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: response.message,
          actions: {
            trades: response.trades,
            watchlist_changes: response.watchlist_changes,
          },
        },
      ]);
      return response;
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "The assistant is unavailable right now.";
      setError(msg);
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: `⚠ ${msg}` },
      ]);
      return null;
    } finally {
      setSending(false);
    }
  }, []);

  return { messages, loadingHistory, sending, error, send };
}
