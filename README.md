# FinAlly — AI Trading Workstation

A visually stunning AI-powered trading workstation: live market data, a simulated portfolio, and an LLM chat assistant that can analyze positions and execute trades via natural language. Built entirely by coding agents as the capstone project for an agentic AI coding course — see [`planning/PLAN.md`](planning/PLAN.md) for the full specification.

## Status

🚧 **In progress.** Only the market data subsystem is built so far.

| Component | Status |
|---|---|
| Market data (simulator + Massive API, price cache, SSE source) | ✅ Done — see [`planning/MARKET_DATA_SUMMARY.md`](planning/MARKET_DATA_SUMMARY.md) |
| Backend API (portfolio, watchlist, chat, SSE endpoint) | ⏳ Not started |
| LLM chat integration | ⏳ Not started |
| Frontend (Next.js terminal UI) | ⏳ Not started |
| Docker / deployment / E2E tests | ⏳ Not started |

## Architecture (target)

Single Docker container, one port (8000): FastAPI serves both the `/api/*` REST + SSE routes and the statically-exported Next.js frontend, backed by a SQLite file. Full rationale in [`planning/PLAN.md`](planning/PLAN.md#3-architecture-overview).

## Repository Layout

```
finally/
├── backend/        # FastAPI uv project
│   └── app/market/ # Market data subsystem (built)
├── planning/        # Project spec and agent-facing docs
│   ├── PLAN.md
│   └── MARKET_DATA_SUMMARY.md
└── CLAUDE.md        # Entry point for coding agents working in this repo
```

`frontend/`, `test/`, `scripts/`, and the `Dockerfile` described in the plan don't exist yet.

## Working on the Backend

```bash
cd backend
uv sync --extra dev
uv run pytest
```

## License

See [LICENSE](LICENSE).
