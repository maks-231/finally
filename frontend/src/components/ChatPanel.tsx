"use client";

import { FormEvent, useEffect, useRef, useState } from "react";
import { ChatMessageRecord } from "@/lib/types";
import { formatCurrency } from "@/lib/format";

interface ChatPanelProps {
  messages: ChatMessageRecord[];
  loadingHistory: boolean;
  sending: boolean;
  onSend: (message: string) => void;
}

function ActionConfirmations({ actions }: { actions: ChatMessageRecord["actions"] }) {
  if (!actions) return null;
  const trades = actions.trades ?? [];
  const watchlistChanges = actions.watchlist_changes ?? [];
  if (trades.length === 0 && watchlistChanges.length === 0) return null;

  return (
    <div className="mt-2 flex flex-col gap-1" data-testid="chat-action-confirmations">
      {trades.map((t, i) => (
        <div
          key={`trade-${i}`}
          className={`rounded border px-2 py-1 text-xs ${
            t.success === false
              ? "border-down/50 bg-down/10 text-down"
              : "border-blue-primary/40 bg-blue-primary/10 text-text-primary"
          }`}
        >
          {t.success === false
            ? `✕ ${t.side.toUpperCase()} ${t.quantity} ${t.ticker} failed${
                t.reason ? ` — ${t.reason}` : ""
              }`
            : `✓ ${t.side.toUpperCase()} ${t.quantity} ${t.ticker}${
                t.price ? ` @ ${formatCurrency(t.price)}` : ""
              }`}
        </div>
      ))}
      {watchlistChanges.map((w, i) => (
        <div
          key={`wl-${i}`}
          className={`rounded border px-2 py-1 text-xs ${
            w.success === false
              ? "border-down/50 bg-down/10 text-down"
              : "border-accent-yellow/40 bg-accent-yellow/10 text-text-primary"
          }`}
        >
          {w.success === false
            ? `✕ ${w.action} ${w.ticker} failed${w.reason ? ` — ${w.reason}` : ""}`
            : `✓ Watchlist: ${w.action === "add" ? "added" : "removed"} ${w.ticker}`}
        </div>
      ))}
    </div>
  );
}

export function ChatPanel({ messages, loadingHistory, sending, onSend }: ChatPanelProps) {
  const [input, setInput] = useState("");
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (!el) return;
    // jsdom (used in tests) doesn't implement scrollTo; guard defensively.
    if (typeof el.scrollTo === "function") {
      el.scrollTo({ top: el.scrollHeight });
    } else {
      el.scrollTop = el.scrollHeight;
    }
  }, [messages, sending]);

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!input.trim() || sending) return;
    onSend(input);
    setInput("");
  }

  return (
    <section className="flex h-full flex-col rounded border border-border-muted bg-bg-panel">
      <h2 className="border-b border-border-muted px-3 py-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
        AI Assistant
      </h2>
      <div ref={scrollRef} className="flex-1 overflow-auto px-3 py-2" data-testid="chat-history">
        {loadingHistory && (
          <p className="text-xs text-text-muted" data-testid="chat-loading-history">
            Loading conversation…
          </p>
        )}
        {!loadingHistory && messages.length === 0 && (
          <p className="text-xs text-text-muted">
            Ask FinAlly about your portfolio, or tell it to make a trade.
          </p>
        )}
        <div className="flex flex-col gap-3">
          {messages.map((m, i) => (
            <div
              key={m.id ?? i}
              data-testid={`chat-message-${m.role}`}
              className={`max-w-[90%] rounded px-3 py-2 text-sm ${
                m.role === "user"
                  ? "self-end bg-blue-primary/20 text-text-primary"
                  : "self-start bg-bg-panel-raised text-text-primary"
              }`}
            >
              <p className="whitespace-pre-wrap">{m.content}</p>
              {m.role === "assistant" && <ActionConfirmations actions={m.actions} />}
            </div>
          ))}
          {sending && (
            <div
              className="self-start rounded bg-bg-panel-raised px-3 py-2 text-sm text-text-muted"
              data-testid="chat-loading-indicator"
            >
              FinAlly is thinking…
            </div>
          )}
        </div>
      </div>
      <form onSubmit={handleSubmit} className="flex gap-2 border-t border-border-muted p-2">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask FinAlly…"
          className="flex-1 rounded border border-border-muted bg-bg-base px-2 py-1.5 text-sm text-text-primary outline-none focus:border-blue-primary"
          data-testid="chat-input"
        />
        <button
          type="submit"
          disabled={sending}
          className="rounded bg-purple-secondary px-3 py-1.5 text-sm font-semibold text-white hover:opacity-90 disabled:opacity-50"
          data-testid="chat-send-button"
        >
          Send
        </button>
      </form>
    </section>
  );
}
