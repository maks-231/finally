export function formatCurrency(value: number, opts?: { decimals?: number }): string {
  const decimals = opts?.decimals ?? 2;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatPercent(value: number, opts?: { decimals?: number }): string {
  const decimals = opts?.decimals ?? 2;
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(decimals)}%`;
}

export function formatSignedCurrency(value: number): string {
  const sign = value > 0 ? "+" : value < 0 ? "-" : "";
  return `${sign}${formatCurrency(Math.abs(value))}`;
}

export function formatQuantity(value: number): string {
  // Fractional shares supported — trim trailing zeros but keep up to 4 decimals.
  return value % 1 === 0 ? value.toFixed(0) : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
}

export function formatTime(timestampSeconds: number): string {
  return new Date(timestampSeconds * 1000).toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });
}
