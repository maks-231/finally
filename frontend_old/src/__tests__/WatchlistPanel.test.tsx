import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { WatchlistPanel } from "@/components/WatchlistPanel";

describe("WatchlistPanel add/remove", () => {
  it("calls onAdd with the typed ticker and clears the input on success", async () => {
    const user = userEvent.setup();
    const onAdd = jest.fn().mockResolvedValue(true);

    render(
      <WatchlistPanel
        tickers={["AAPL"]}
        prices={{}}
        history={{}}
        selectedTicker={null}
        onSelect={jest.fn()}
        onAdd={onAdd}
        onRemove={jest.fn()}
        error={null}
      />,
    );

    const input = screen.getByTestId("watchlist-add-input");
    await user.type(input, "tsla");
    await user.click(screen.getByTestId("watchlist-add-button"));

    expect(onAdd).toHaveBeenCalledWith("TSLA");
    expect(input).toHaveValue("");
  });

  it("does not clear the input if onAdd fails", async () => {
    const user = userEvent.setup();
    const onAdd = jest.fn().mockResolvedValue(false);

    render(
      <WatchlistPanel
        tickers={["AAPL"]}
        prices={{}}
        history={{}}
        selectedTicker={null}
        onSelect={jest.fn()}
        onAdd={onAdd}
        onRemove={jest.fn()}
        error={null}
      />,
    );

    const input = screen.getByTestId("watchlist-add-input");
    await user.type(input, "XXXX");
    await user.click(screen.getByTestId("watchlist-add-button"));

    expect(onAdd).toHaveBeenCalledWith("XXXX");
    expect(input).toHaveValue("XXXX");
  });

  it("calls onRemove when a row's remove button is clicked", async () => {
    const user = userEvent.setup();
    const onRemove = jest.fn();

    render(
      <WatchlistPanel
        tickers={["AAPL", "GOOGL"]}
        prices={{}}
        history={{}}
        selectedTicker={null}
        onSelect={jest.fn()}
        onAdd={jest.fn()}
        onRemove={onRemove}
        error={null}
      />,
    );

    await user.click(screen.getByTestId("remove-GOOGL"));
    expect(onRemove).toHaveBeenCalledWith("GOOGL");
  });

  it("renders an empty state when the watchlist has no tickers", () => {
    render(
      <WatchlistPanel
        tickers={[]}
        prices={{}}
        history={{}}
        selectedTicker={null}
        onSelect={jest.fn()}
        onAdd={jest.fn()}
        onRemove={jest.fn()}
        error={null}
      />,
    );
    expect(screen.getByText(/watchlist is empty/i)).toBeInTheDocument();
  });

  it("surfaces an error message from the watchlist hook", () => {
    render(
      <WatchlistPanel
        tickers={[]}
        prices={{}}
        history={{}}
        selectedTicker={null}
        onSelect={jest.fn()}
        onAdd={jest.fn()}
        onRemove={jest.fn()}
        error="Ticker not found"
      />,
    );
    expect(screen.getByTestId("watchlist-error")).toHaveTextContent("Ticker not found");
  });
});
