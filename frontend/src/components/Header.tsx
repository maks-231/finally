import { ConnectionState } from "@/lib/types";
import { formatCurrency } from "@/lib/format";
import { ConnectionStatusDot } from "./ConnectionStatusDot";

interface HeaderProps {
  totalValue: number | null;
  cashBalance: number | null;
  connectionState: ConnectionState;
}

export function Header({ totalValue, cashBalance, connectionState }: HeaderProps) {
  return (
    <header className="flex items-center justify-between border-b border-border-muted bg-bg-panel px-6 py-3">
      <div className="flex items-center gap-3">
        <span className="text-lg font-bold tracking-tight text-accent-yellow">FinAlly</span>
        <span className="hidden text-xs text-text-muted sm:inline">AI Trading Workstation</span>
      </div>

      <div className="flex items-center gap-6">
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wide text-text-muted">Total Value</div>
          <div className="font-mono text-base font-semibold text-text-primary" data-testid="header-total-value">
            {totalValue === null ? "—" : formatCurrency(totalValue)}
          </div>
        </div>
        <div className="text-right">
          <div className="text-[10px] uppercase tracking-wide text-text-muted">Cash</div>
          <div className="font-mono text-base text-blue-primary" data-testid="header-cash-balance">
            {cashBalance === null ? "—" : formatCurrency(cashBalance)}
          </div>
        </div>
        <ConnectionStatusDot state={connectionState} />
      </div>
    </header>
  );
}
