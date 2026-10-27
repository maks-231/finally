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
import { PortfolioSnapshot } from "@/lib/types";
import { formatCurrency } from "@/lib/format";

interface PnlChartProps {
  snapshots: PortfolioSnapshot[];
}

export function PnlChart({ snapshots }: PnlChartProps) {
  const data = snapshots.map((s) => ({
    time: new Date(s.recorded_at).getTime(),
    total_value: s.total_value,
  }));
  const isUp = data.length > 1 && data[data.length - 1].total_value >= data[0].total_value;

  return (
    <section className="flex h-full flex-col rounded border border-border-muted bg-bg-panel p-3">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
        Portfolio Value
      </h2>
      <div className="flex-1" data-testid="pnl-chart">
        {data.length < 2 ? (
          <div className="flex h-full items-center justify-center text-xs text-text-muted">
            Not enough history yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data} margin={{ top: 4, right: 8, bottom: 0, left: 0 }}>
              <CartesianGrid stroke="var(--color-border-subtle)" strokeDasharray="3 3" vertical={false} />
              <XAxis
                dataKey="time"
                tickFormatter={(v: number) =>
                  new Date(v).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
                }
                stroke="var(--color-text-muted)"
                fontSize={10}
                tickLine={false}
              />
              <YAxis
                domain={["auto", "auto"]}
                stroke="var(--color-text-muted)"
                fontSize={10}
                tickLine={false}
                width={65}
                tickFormatter={(v: number) => formatCurrency(v)}
              />
              <Tooltip
                contentStyle={{
                  background: "var(--color-bg-panel-raised)",
                  border: "1px solid var(--color-border-muted)",
                  fontSize: 12,
                }}
                labelFormatter={(v) => new Date(Number(v)).toLocaleString()}
                formatter={(value) => [formatCurrency(Number(value)), "Total Value"]}
              />
              <Line
                type="monotone"
                dataKey="total_value"
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
