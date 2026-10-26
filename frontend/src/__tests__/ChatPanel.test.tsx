import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ChatPanel } from "@/components/ChatPanel";
import { ChatMessageRecord } from "@/lib/types";

describe("ChatPanel", () => {
  it("shows a loading indicator while chat history is being restored", () => {
    render(<ChatPanel messages={[]} loadingHistory sending={false} onSend={jest.fn()} />);
    expect(screen.getByTestId("chat-loading-history")).toBeInTheDocument();
  });

  it("renders persisted conversation history on mount", () => {
    const messages: ChatMessageRecord[] = [
      { role: "user", content: "What's my portfolio worth?" },
      { role: "assistant", content: "Your portfolio is worth $12,000." },
    ];
    render(<ChatPanel messages={messages} loadingHistory={false} sending={false} onSend={jest.fn()} />);

    const userMsgs = screen.getAllByTestId("chat-message-user");
    const assistantMsgs = screen.getAllByTestId("chat-message-assistant");
    expect(userMsgs[0]).toHaveTextContent("What's my portfolio worth?");
    expect(assistantMsgs[0]).toHaveTextContent("Your portfolio is worth $12,000.");
  });

  it("shows a 'thinking' indicator while awaiting the assistant's response", () => {
    render(<ChatPanel messages={[]} loadingHistory={false} sending onSend={jest.fn()} />);
    expect(screen.getByTestId("chat-loading-indicator")).toBeInTheDocument();
  });

  it("renders inline trade and watchlist confirmations attached to an assistant message", () => {
    const messages: ChatMessageRecord[] = [
      {
        role: "assistant",
        content: "Bought 10 AAPL and added TSLA to your watchlist.",
        actions: {
          trades: [{ ticker: "AAPL", side: "buy", quantity: 10, price: 190, success: true }],
          watchlist_changes: [{ ticker: "TSLA", action: "add", success: true }],
        },
      },
    ];
    render(<ChatPanel messages={messages} loadingHistory={false} sending={false} onSend={jest.fn()} />);

    const confirmations = screen.getByTestId("chat-action-confirmations");
    expect(confirmations).toHaveTextContent("BUY 10 AAPL @ $190.00");
    expect(confirmations).toHaveTextContent("added TSLA");
  });

  it("renders a failed trade confirmation distinctly", () => {
    const messages: ChatMessageRecord[] = [
      {
        role: "assistant",
        content: "I couldn't complete that trade.",
        actions: {
          trades: [
            {
              ticker: "AAPL",
              side: "buy",
              quantity: 1000,
              success: false,
              reason: "Insufficient cash balance for this trade.",
            },
          ],
        },
      },
    ];
    render(<ChatPanel messages={messages} loadingHistory={false} sending={false} onSend={jest.fn()} />);
    const confirmations = screen.getByTestId("chat-action-confirmations");
    expect(confirmations).toHaveTextContent("Insufficient cash balance for this trade.");
    expect(confirmations).toHaveTextContent("failed");
    expect(confirmations).not.toHaveTextContent("✓");
  });

  it("does not render a failed trade with success styling or checkmark", () => {
    const messages: ChatMessageRecord[] = [
      {
        role: "assistant",
        content: "I couldn't complete that trade.",
        actions: {
          trades: [
            {
              ticker: "AAPL",
              side: "buy",
              quantity: 999999,
              success: false,
              reason: "Insufficient cash balance for this trade.",
            },
          ],
        },
      },
    ];
    render(<ChatPanel messages={messages} loadingHistory={false} sending={false} onSend={jest.fn()} />);
    const confirmations = screen.getByTestId("chat-action-confirmations");
    expect(confirmations.textContent).toContain("✕");
    expect(confirmations.textContent).not.toContain("✓");
  });

  it("submits a message via the input and clears it", async () => {
    const user = userEvent.setup();
    const onSend = jest.fn();
    render(<ChatPanel messages={[]} loadingHistory={false} sending={false} onSend={onSend} />);

    const input = screen.getByTestId("chat-input");
    await user.type(input, "Buy 5 shares of AAPL");
    await user.click(screen.getByTestId("chat-send-button"));

    expect(onSend).toHaveBeenCalledWith("Buy 5 shares of AAPL");
    expect(input).toHaveValue("");
  });
});
