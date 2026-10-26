import { ConnectionState } from "@/lib/types";

const STATE_CONFIG: Record<ConnectionState, { color: string; label: string }> = {
  connected: { color: "bg-up", label: "Connected" },
  reconnecting: { color: "bg-accent-yellow", label: "Reconnecting" },
  disconnected: { color: "bg-down", label: "Disconnected" },
};

export function ConnectionStatusDot({ state }: { state: ConnectionState }) {
  const { color, label } = STATE_CONFIG[state];
  return (
    <div className="flex items-center gap-2" data-testid="connection-status" data-state={state}>
      <span
        className={`inline-block h-2.5 w-2.5 rounded-full ${color} ${
          state === "reconnecting" ? "animate-pulse" : ""
        }`}
        aria-hidden
      />
      <span className="text-xs text-text-muted uppercase tracking-wide">{label}</span>
    </div>
  );
}
