"use client";

import { useState } from "react";
import { Header } from "@/components/Header";
import { WatchlistPanel } from "@/components/WatchlistPanel";
import { MainChart } from "@/components/MainChart";
import { PortfolioHeatmap } from "@/components/PortfolioHeatmap";
import { PnlChart } from "@/components/PnlChart";
import { PositionsTable } from "@/components/PositionsTable";
import { TradeBar } from "@/components/TradeBar";
import { ChatPanel } from "@/components/ChatPanel";
import { usePriceStream } from "@/hooks/usePriceStream";
import { usePortfolio } from "@/hooks/usePortfolio";
import { useWatchlist } from "@/hooks/useWatchlist";
import { usePortfolioHistory } from "@/hooks/usePortfolioHistory";
import { useChat } from "@/hooks/useChat";

export default function Home() {
  const { prices, history, connectionState } = usePriceStream();
  const { portfolio, trade, tradeError, tradePending, setTradeError } = usePortfolio();
  const { watchlist, add, remove, error: watchlistError, refetch: refetchWatchlist } = useWatchlist();
  const { history: portfolioHistory } = usePortfolioHistory();
  const { messages, loadingHistory, sending, send } = useChat();

  // Chat-driven watchlist changes (e.g. "add DIS to the watchlist") are
  // executed server-side by POST /api/chat, but useWatchlist has no polling
  // loop of its own — it only refetches after its own add/remove calls. So
  // after a chat response comes back, explicitly refetch the watchlist if
  // the assistant made any successful watchlist change.
  async function handleChatSend(message: string) {
    const response = await send(message);
    const hasSuccessfulWatchlistChange = response?.watchlist_changes?.some(
      (change) => change.success !== false,
    );
    if (hasSuccessfulWatchlistChange) {
      await refetchWatchlist();
    }
  }

  const watchlistTickers = watchlist.map((w) => w.ticker);
  const [selectedTicker, setSelectedTicker] = useState<string | null>(null);
  // Derive the effective selection at render time rather than syncing it via
  // an effect: falls back to the first watchlist ticker until the user picks
  // one explicitly, and naturally re-falls-back after a removal clears it.
  const effectiveSelectedTicker = selectedTicker ?? watchlistTickers[0] ?? null;

  async function handleRemove(ticker: string) {
    await remove(ticker);
    if (selectedTicker === ticker) {
      setSelectedTicker(null);
    }
  }

  return (
    <div className="flex h-screen flex-col bg-bg-base">
      <Header
        totalValue={portfolio?.total_value ?? null}
        cashBalance={portfolio?.cash_balance ?? null}
        connectionState={connectionState}
      />

      <main className="grid flex-1 grid-cols-[300px_minmax(0,1fr)_340px] gap-3 overflow-hidden p-3">
        <div className="min-h-0">
          <WatchlistPanel
            tickers={watchlistTickers}
            prices={prices}
            history={history}
            selectedTicker={effectiveSelectedTicker}
            onSelect={setSelectedTicker}
            onAdd={add}
            onRemove={handleRemove}
            error={watchlistError}
          />
        </div>

        <div className="grid min-h-0 grid-rows-[2fr_1fr_1fr] gap-3">
          <div className="min-h-0">
            <MainChart
              ticker={effectiveSelectedTicker}
              points={effectiveSelectedTicker ? history[effectiveSelectedTicker] ?? [] : []}
            />
          </div>

          <div className="grid min-h-0 grid-cols-2 gap-3">
            <PortfolioHeatmap positions={portfolio?.positions ?? []} />
            <PnlChart snapshots={portfolioHistory} />
          </div>

          <div className="flex min-h-0 flex-col gap-3">
            <div className="min-h-0 flex-1">
              <PositionsTable positions={portfolio?.positions ?? []} />
            </div>
            <TradeBar
              defaultTicker={effectiveSelectedTicker}
              onTrade={async (ticker, quantity, side) => {
                setTradeError(null);
                return trade(ticker, quantity, side);
              }}
              pending={tradePending}
              error={tradeError}
            />
          </div>
        </div>

        <div className="min-h-0">
          <ChatPanel messages={messages} loadingHistory={loadingHistory} sending={sending} onSend={handleChatSend} />
        </div>
      </main>
    </div>
  );
}
