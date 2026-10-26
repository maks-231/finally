import { render, screen } from "@testing-library/react";
import { WatchlistRow } from "@/components/WatchlistRow";
import { PriceUpdate } from "@/lib/types";

function makeUpdate(overrides: Partial<PriceUpdate>): PriceUpdate {
  return {
    ticker: "AAPL",
    price: 190,
    previous_price: 189,
    timestamp: 1000,
    change: 1,
    change_percent: 0.53,
    direction: "up",
    ...overrides,
  };
}

describe("WatchlistRow price flash animation", () => {
  it("does not apply a flash class on first render", () => {
    render(
      <table>
        <tbody>
          <WatchlistRow
            ticker="AAPL"
            priceUpdate={makeUpdate({})}
            history={[]}
            selected={false}
            onSelect={jest.fn()}
            onRemove={jest.fn()}
          />
        </tbody>
      </table>,
    );
    const flashEl = screen.getByTestId("price-flash-AAPL");
    expect(flashEl.className).not.toMatch(/price-flash/);
  });

  it("applies price-flash-up when a new, higher-priced tick arrives", () => {
    const { rerender } = render(
      <table>
        <tbody>
          <WatchlistRow
            ticker="AAPL"
            priceUpdate={makeUpdate({ timestamp: 1000, price: 190, direction: "up" })}
            history={[]}
            selected={false}
            onSelect={jest.fn()}
            onRemove={jest.fn()}
          />
        </tbody>
      </table>,
    );

    rerender(
      <table>
        <tbody>
          <WatchlistRow
            ticker="AAPL"
            priceUpdate={makeUpdate({ timestamp: 2000, price: 191, previous_price: 190, direction: "up" })}
            history={[]}
            selected={false}
            onSelect={jest.fn()}
            onRemove={jest.fn()}
          />
        </tbody>
      </table>,
    );

    const flashEl = screen.getByTestId("price-flash-AAPL");
    expect(flashEl.className).toMatch(/price-flash-up/);
    expect(flashEl).toHaveTextContent("$191.00");
  });

  it("applies price-flash-down when a new, lower-priced tick arrives", () => {
    const { rerender } = render(
      <table>
        <tbody>
          <WatchlistRow
            ticker="AAPL"
            priceUpdate={makeUpdate({ timestamp: 1000, price: 190, direction: "up" })}
            history={[]}
            selected={false}
            onSelect={jest.fn()}
            onRemove={jest.fn()}
          />
        </tbody>
      </table>,
    );

    rerender(
      <table>
        <tbody>
          <WatchlistRow
            ticker="AAPL"
            priceUpdate={makeUpdate({ timestamp: 2000, price: 185, previous_price: 190, direction: "down" })}
            history={[]}
            selected={false}
            onSelect={jest.fn()}
            onRemove={jest.fn()}
          />
        </tbody>
      </table>,
    );

    const flashEl = screen.getByTestId("price-flash-AAPL");
    expect(flashEl.className).toMatch(/price-flash-down/);
  });

  it("does not flash when the tick is flat (no price change)", () => {
    const { rerender } = render(
      <table>
        <tbody>
          <WatchlistRow
            ticker="AAPL"
            priceUpdate={makeUpdate({ timestamp: 1000, price: 190, direction: "up" })}
            history={[]}
            selected={false}
            onSelect={jest.fn()}
            onRemove={jest.fn()}
          />
        </tbody>
      </table>,
    );

    rerender(
      <table>
        <tbody>
          <WatchlistRow
            ticker="AAPL"
            priceUpdate={makeUpdate({ timestamp: 2000, price: 190, previous_price: 190, direction: "flat" })}
            history={[]}
            selected={false}
            onSelect={jest.fn()}
            onRemove={jest.fn()}
          />
        </tbody>
      </table>,
    );

    const flashEl = screen.getByTestId("price-flash-AAPL");
    expect(flashEl.className).not.toMatch(/price-flash/);
  });
});
