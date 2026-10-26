"use client";

import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PricePoint } from "@/lib/types";
import { formatCurrency, formatTime } from "@/lib/format";

interface MainChartProps {
  ticker: string | null;
  points: PricePoint[];
}

export function MainChart({ ticker, points }: MainChartProps) {
  const data = points.map((p) => ({ time: p.timestamp, price: p.price }));
  const isUp = data.length > 1 && data[data.length - 1].price >= data[0].price;

  return (
    <section className="flex h-full flex-col rounded border border-border-muted bg-bg-panel p-3">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-xs font-semibold uppercase tracking-wide text-text-muted">
          {ticker ? `${ticker} — Price` : "Select a ticker"}
        </h2>
        {data.length > 0 && (
          <span className="font-mono text-sm text-text-primary" data-testid="main-chart-latest-price">
            {formatCurrency(data[data.length - 1].price)}
          </span>
        )}
      </div>
      <div className="flex-1" data-testid="main-chart">
        {data.length < 2 ? (
          <div className="flex h-full items-center justify-center text-xs text-text-muted">
            {ticker ? "Collecting live price data…" : "Click a watchlist ticker to chart it."}
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--color-border-subtle)" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="time"
                tickFormatter={(v: number) => formatTime(v)}
                stroke="var(--color-text-muted)"
                fontSize={10}
                tickLine={false}
              />
              <YAxis
                domain={["auto", "auto"]}
                stroke="var(--color-text-muted)"
                fontSize={10}
                tickLine={false}
                width={60}
                tickFormatter={(v: number) => formatCurrency(v)}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--color-bg-panel-raised)",
                  border: "1px solid var(--color-border-muted)",
                  fontSize: 12,
                }}
                labelFormatter={(v) => formatTime(Number(v))}
                formatter={(value) => [formatCurrency(Number(value)), "Price"]}
              />
              <Line
                type="monotone"
                dataKey="price"
                stroke={isUp ? "var(--color-up)" : "var(--color-down)"}
                strokeWidth={1.75}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}
