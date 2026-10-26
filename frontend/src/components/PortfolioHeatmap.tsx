"use client";

import { ResponsiveContainer, Treemap } from "recharts";
import { Position } from "@/lib/types";
import { formatPercent } from "@/lib/format";

interface PortfolioHeatmapProps {
  positions: Position[];
}

interface HeatmapNode {
  name: string;
  size: number;
  pnlPercent: number;
  pnl: number;
  [key: string]: string | number;
}

function pnlColor(pnlPercent: number): string {
  if (pnlPercent > 0) {
    // scale green intensity with magnitude, capped
    const intensity = Math.min(Math.abs(pnlPercent) / 10, 1);
    return `rgba(46, 204, 113, ${0.25 + intensity * 0.6})`;
  }
  if (pnlPercent < 0) {
    const intensity = Math.min(Math.abs(pnlPercent) / 10, 1);
    return `rgba(239, 68, 68, ${0.25 + intensity * 0.6})`;
  }
  return "rgba(139, 148, 158, 0.3)";
}

function HeatmapCell(props: {
  x?: number;
  y?: number;
  width?: number;
  height?: number;
  name?: string;
  pnlPercent?: number;
  pnl?: number;
}) {
  const { x = 0, y = 0, width = 0, height = 0, name, pnlPercent = 0, pnl = 0 } = props;
  if (!name || width <= 0 || height <= 0) return null;

  const showLabel = width > 42 && height > 28;

  return (
    <g data-testid={`heatmap-cell-${name}`}>
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill={pnlColor(pnlPercent)}
        stroke="var(--color-border-muted)"
        strokeWidth={1}
      />
      {showLabel && (
        <>
          <text x={x + 6} y={y + 16} fontSize={12} fontWeight={600} fill="var(--color-text-primary)">
            {name}
          </text>
          <text
            x={x + 6}
            y={y + 30}
            fontSize={10}
            fill={pnl >= 0 ? "var(--color-up)" : "var(--color-down)"}
          >
            {formatPercent(pnlPercent)}
          </text>
        </>
      )}
    </g>
  );
}

export function PortfolioHeatmap({ positions }: PortfolioHeatmapProps) {
  const data: HeatmapNode[] = positions
    .map((p) => ({
      name: p.ticker,
      size: Math.max(p.quantity * p.current_price, 0.01),
      pnlPercent: p.unrealized_pnl_percent,
      pnl: p.unrealized_pnl,
    }))
    .filter((d) => Number.isFinite(d.size));

  return (
    <section className="flex h-full flex-col rounded border border-border-muted bg-bg-panel p-3">
      <h2 className="mb-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
        Portfolio Heatmap
      </h2>
      <div className="flex-1" data-testid="portfolio-heatmap">
        {data.length === 0 ? (
          <div className="flex h-full items-center justify-center text-xs text-text-muted">
            No open positions yet.
          </div>
        ) : (
          <ResponsiveContainer width="100%" height="100%">
            <Treemap
              data={data}
              dataKey="size"
              stroke="var(--color-border-muted)"
              isAnimationActive={false}
              content={<HeatmapCell />}
            />
          </ResponsiveContainer>
        )}
      </div>
    </section>
  );
}
