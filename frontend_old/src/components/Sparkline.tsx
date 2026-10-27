import { PricePoint } from "@/lib/types";

interface SparklineProps {
  points: PricePoint[];
  width?: number;
  height?: number;
  positive: boolean;
}

/**
 * Lightweight SVG sparkline — intentionally not Recharts here since the
 * watchlist can render many of these simultaneously and they just need a
 * cheap polyline, not a full chart.
 */
export function Sparkline({ points, width = 72, height = 24, positive }: SparklineProps) {
  if (points.length < 2) {
    return (
      <div
        className="flex items-center justify-center text-[10px] text-text-muted"
        style={{ width, height }}
        data-testid="sparkline-empty"
      >
        collecting…
      </div>
    );
  }

  const prices = points.map((p) => p.price);
  const min = Math.min(...prices);
  const max = Math.max(...prices);
  const range = max - min || 1;

  const coords = points.map((p, i) => {
    const x = (i / (points.length - 1)) * width;
    const y = height - ((p.price - min) / range) * height;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  return (
    <svg width={width} height={height} className="overflow-visible" data-testid="sparkline">
      <polyline
        points={coords.join(" ")}
        fill="none"
        stroke={positive ? "var(--color-up)" : "var(--color-down)"}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
      />
    </svg>
  );
}
