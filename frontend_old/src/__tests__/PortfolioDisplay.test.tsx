import { render, screen } from "@testing-library/react";
import { PositionsTable } from "@/components/PositionsTable";
import { Header } from "@/components/Header";
import { Position } from "@/lib/types";

const positions: Position[] = [
  {
    ticker: "AAPL",
    quantity: 10,
    avg_cost: 150,
    current_price: 190,
    unrealized_pnl: 400,
    unrealized_pnl_percent: 26.67,
  },
  {
    ticker: "TSLA",
    quantity: 2.5,
    avg_cost: 300,
    current_price: 250,
    unrealized_pnl: -125,
    unrealized_pnl_percent: -16.67,
  },
];

describe("PositionsTable calculations", () => {
  it("renders each position's quantity, cost basis, price and P&L correctly", () => {
    render(<PositionsTable positions={positions} />);

    const aaplRow = screen.getByTestId("position-row-AAPL");
    expect(aaplRow).toHaveTextContent("AAPL");
    expect(aaplRow).toHaveTextContent("10"); // quantity
    expect(aaplRow).toHaveTextContent("$150.00"); // avg cost
    expect(aaplRow).toHaveTextContent("$190.00"); // current price
    expect(screen.getByTestId("position-pnl-AAPL")).toHaveTextContent("+$400.00");

    const tslaRow = screen.getByTestId("position-row-TSLA");
    expect(tslaRow).toHaveTextContent("2.5"); // fractional share quantity preserved
    expect(screen.getByTestId("position-pnl-TSLA")).toHaveTextContent("-$125.00");
  });

  it("colors profitable positions green and losing positions red", () => {
    render(<PositionsTable positions={positions} />);
    expect(screen.getByTestId("position-pnl-AAPL").className).toMatch(/text-up/);
    expect(screen.getByTestId("position-pnl-TSLA").className).toMatch(/text-down/);
  });

  it("shows an empty state with no positions", () => {
    render(<PositionsTable positions={[]} />);
    expect(screen.getByText(/no open positions/i)).toBeInTheDocument();
  });
});

describe("Header portfolio summary", () => {
  it("renders total value and cash balance formatted as currency", () => {
    render(<Header totalValue={12345.67} cashBalance={5000} connectionState="connected" />);
    expect(screen.getByTestId("header-total-value")).toHaveTextContent("$12,345.67");
    expect(screen.getByTestId("header-cash-balance")).toHaveTextContent("$5,000.00");
  });

  it("renders a placeholder while portfolio data is still loading", () => {
    render(<Header totalValue={null} cashBalance={null} connectionState="disconnected" />);
    expect(screen.getByTestId("header-total-value")).toHaveTextContent("—");
    expect(screen.getByTestId("header-cash-balance")).toHaveTextContent("—");
  });

  it("reflects the connection state in the status dot", () => {
    render(<Header totalValue={0} cashBalance={0} connectionState="reconnecting" />);
    expect(screen.getByTestId("connection-status")).toHaveAttribute("data-state", "reconnecting");
  });
});
