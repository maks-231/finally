import { Position } from "@/lib/types";
import { formatCurrency, formatPercent, formatQuantity, formatSignedCurrency } from "@/lib/format";

interface PositionsTableProps {
  positions: Position[];
}

export function PositionsTable({ positions }: PositionsTableProps) {
  return (
    <section className="flex h-full flex-col rounded border border-border-muted bg-bg-panel">
      <h2 className="border-b border-border-muted px-3 py-2 text-xs font-semibold uppercase tracking-wide text-text-muted">
        Positions
      </h2>
      <div className="flex-1 overflow-auto">
        <table className="w-full border-collapse text-sm" data-testid="positions-table">
          <thead>
            <tr className="text-left text-[10px] uppercase tracking-wide text-text-muted">
              <th className="px-3 py-1.5">Ticker</th>
              <th className="px-3 py-1.5 text-right">Qty</th>
              <th className="px-3 py-1.5 text-right">Avg Cost</th>
              <th className="px-3 py-1.5 text-right">Price</th>
              <th className="px-3 py-1.5 text-right">Unrealized P&L</th>
              <th className="px-3 py-1.5 text-right">% Chg</th>
            </tr>
          </thead>
          <tbody>
            {positions.map((p) => (
              <tr
                key={p.ticker}
                className="border-b border-border-subtle font-mono"
                data-testid={`position-row-${p.ticker}`}
              >
                <td className="px-3 py-2 font-sans font-semibold text-text-primary">{p.ticker}</td>
                <td className="px-3 py-2 text-right">{formatQuantity(p.quantity)}</td>
                <td className="px-3 py-2 text-right">{formatCurrency(p.avg_cost)}</td>
                <td className="px-3 py-2 text-right">{formatCurrency(p.current_price)}</td>
                <td
                  className={`px-3 py-2 text-right ${p.unrealized_pnl >= 0 ? "text-up" : "text-down"}`}
                  data-testid={`position-pnl-${p.ticker}`}
                >
                  {formatSignedCurrency(p.unrealized_pnl)}
                </td>
                <td
                  className={`px-3 py-2 text-right ${p.unrealized_pnl_percent >= 0 ? "text-up" : "text-down"}`}
                >
                  {formatPercent(p.unrealized_pnl_percent)}
                </td>
              </tr>
            ))}
            {positions.length === 0 && (
              <tr>
                <td colSpan={6} className="px-3 py-6 text-center text-xs font-sans text-text-muted">
                  No open positions. Place a trade to get started.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </section>
  );
}
