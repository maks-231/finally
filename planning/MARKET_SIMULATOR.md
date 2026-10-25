# Market Simulator Design

Approach and code structure for simulating realistic multi-ticker stock prices when no `MASSIVE_API_KEY` is configured — the default, zero-config path for this project. This describes the simulator as actually implemented in `backend/app/market/simulator.py` + `seed_prices.py` (73 passing tests, 98% coverage on `simulator.py`). It supersedes `planning/archive/MARKET_SIMULATOR.md`, whose correlation-constant names (`DEFAULT_CORR`) were superseded during the original build's code review.

## Overview

The simulator uses **Geometric Brownian Motion (GBM)** — the same stochastic process underlying Black-Scholes option pricing. Prices evolve continuously with random noise, can never go negative (the process is multiplicative via `exp()`), and produce the lognormal price-path distribution seen in real markets. Updates run at ~500ms intervals via an `asyncio` background task, producing a continuous stream of small price changes that feels alive on a live dashboard.

## GBM Math

At each time step:

```
S(t+dt) = S(t) * exp((mu - sigma^2/2) * dt + sigma * sqrt(dt) * Z)
```

- `S(t)` — current price
- `mu` — annualized drift (expected return), e.g. `0.05` = 5%/year
- `sigma` — annualized volatility, e.g. `0.20` = 20%/year
- `dt` — time step as a fraction of a trading year
- `Z` — a (correlated) standard normal random draw

### Choosing `dt`

For 500ms ticks over a 252-day trading year at 6.5 hours/day:

```
TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600 = 5,896,800
DEFAULT_DT = 0.5 / 5,896,800 ≈ 8.48e-8
```

This tiny `dt` produces sub-cent moves per tick that compound naturally into realistic intraday ranges over the course of a session — a ticker with `sigma=0.50` (TSLA) drifts through roughly the right intraday range over minutes of wall-clock time.

## Correlated Moves

Real stocks don't move independently — sector peers tend to move together. The simulator builds a correlation matrix from sector groupings and applies a **Cholesky decomposition** to turn independent normal draws into correlated ones:

```
L = cholesky(correlation_matrix)
Z_correlated = L @ Z_independent
```

Cholesky decomposition requires the input matrix to be positive semi-definite, which any valid correlation matrix (1s on the diagonal, pairwise correlations in `[-1, 1]`, symmetric) satisfies.

### Correlation structure (as implemented)

```python
CORRELATION_GROUPS: dict[str, set[str]] = {
    "tech": {"AAPL", "GOOGL", "MSFT", "AMZN", "META", "NVDA", "NFLX"},
    "finance": {"JPM", "V"},
}

INTRA_TECH_CORR = 0.6      # tech stocks move together
INTRA_FINANCE_CORR = 0.5   # finance stocks move together
CROSS_GROUP_CORR = 0.3     # cross-sector and unknown-ticker baseline
TSLA_CORR = 0.3            # TSLA checked against ANY other ticker first — it's a loner
```

Pairwise lookup (`_pairwise_correlation`) checks TSLA first — even though it's a member of no explicit group, any pair involving TSLA gets `0.3` regardless of the other ticker's sector — then falls through to tech/finance intra-group checks, defaulting to `CROSS_GROUP_CORR` otherwise. A ticker added at runtime that isn't in either group correlates with everything at the `0.3` baseline.

## Random Shock Events

Each tick, each ticker independently has a small chance of a sudden 2–5% jump, for visual drama on the dashboard:

```python
event_probability = 0.001   # ~0.1% per ticker per tick

if random.random() < event_probability:
    shock_magnitude = random.uniform(0.02, 0.05)
    shock_sign = random.choice([-1, 1])
    price *= 1 + shock_magnitude * shock_sign
```

At 2 ticks/sec, `0.001` probability means an event roughly every 500 seconds *per ticker*. With 10 tickers in the default watchlist, expect a visible event somewhere in the grid roughly every 50 seconds — frequent enough to be interesting without feeling chaotic.

## Seed Data

```python
SEED_PRICES: dict[str, float] = {
    "AAPL": 190.00, "GOOGL": 175.00, "MSFT": 420.00, "AMZN": 185.00,
    "TSLA": 250.00, "NVDA": 800.00, "META": 500.00, "JPM": 195.00,
    "V": 280.00, "NFLX": 600.00,
}

TICKER_PARAMS: dict[str, dict[str, float]] = {
    "AAPL":  {"sigma": 0.22, "mu": 0.05},
    "GOOGL": {"sigma": 0.25, "mu": 0.05},
    "MSFT":  {"sigma": 0.20, "mu": 0.05},
    "AMZN":  {"sigma": 0.28, "mu": 0.05},
    "TSLA":  {"sigma": 0.50, "mu": 0.03},   # high volatility
    "NVDA":  {"sigma": 0.40, "mu": 0.08},   # high volatility, strong drift
    "META":  {"sigma": 0.30, "mu": 0.05},
    "JPM":   {"sigma": 0.18, "mu": 0.04},   # low volatility (bank)
    "V":     {"sigma": 0.17, "mu": 0.04},   # low volatility (payments)
    "NFLX":  {"sigma": 0.35, "mu": 0.05},
}

DEFAULT_PARAMS: dict[str, float] = {"sigma": 0.25, "mu": 0.05}
```

A ticker added at runtime that isn't in `SEED_PRICES` starts at a random price drawn uniformly from `$50`–`$300`, with `DEFAULT_PARAMS` volatility/drift.

## Implementation — `GBMSimulator`

```python
import math, random
import numpy as np

class GBMSimulator:
    TRADING_SECONDS_PER_YEAR = 252 * 6.5 * 3600  # 5,896,800
    DEFAULT_DT = 0.5 / TRADING_SECONDS_PER_YEAR    # ~8.48e-8

    def __init__(self, tickers: list[str], dt: float = DEFAULT_DT,
                 event_probability: float = 0.001) -> None:
        self._dt = dt
        self._event_prob = event_probability
        self._tickers: list[str] = []
        self._prices: dict[str, float] = {}
        self._params: dict[str, dict[str, float]] = {}
        self._cholesky: np.ndarray | None = None
        for ticker in tickers:
            self._add_ticker_internal(ticker)
        self._rebuild_cholesky()

    def step(self) -> dict[str, float]:
        """Advance all tickers by one time step. Hot path — called every 500ms."""
        n = len(self._tickers)
        if n == 0:
            return {}

        z_independent = np.random.standard_normal(n)
        z = self._cholesky @ z_independent if self._cholesky is not None else z_independent

        result: dict[str, float] = {}
        for i, ticker in enumerate(self._tickers):
            mu, sigma = self._params[ticker]["mu"], self._params[ticker]["sigma"]
            drift = (mu - 0.5 * sigma**2) * self._dt
            diffusion = sigma * math.sqrt(self._dt) * z[i]
            self._prices[ticker] *= math.exp(drift + diffusion)

            if random.random() < self._event_prob:
                shock = random.uniform(0.02, 0.05) * random.choice([-1, 1])
                self._prices[ticker] *= 1 + shock

            result[ticker] = round(self._prices[ticker], 2)
        return result

    def add_ticker(self, ticker: str) -> None:
        if ticker in self._prices:
            return
        self._add_ticker_internal(ticker)
        self._rebuild_cholesky()     # O(n^2), but n < 50 — negligible

    def remove_ticker(self, ticker: str) -> None:
        if ticker not in self._prices:
            return
        self._tickers.remove(ticker)
        del self._prices[ticker]
        del self._params[ticker]
        self._rebuild_cholesky()

    def get_price(self, ticker: str) -> float | None:
        return self._prices.get(ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    def _add_ticker_internal(self, ticker: str) -> None:
        self._tickers.append(ticker)
        self._prices[ticker] = SEED_PRICES.get(ticker, random.uniform(50.0, 300.0))
        self._params[ticker] = TICKER_PARAMS.get(ticker, dict(DEFAULT_PARAMS))

    def _rebuild_cholesky(self) -> None:
        n = len(self._tickers)
        if n <= 1:
            self._cholesky = None
            return
        corr = np.eye(n)
        for i in range(n):
            for j in range(i + 1, n):
                rho = self._pairwise_correlation(self._tickers[i], self._tickers[j])
                corr[i, j] = corr[j, i] = rho
        self._cholesky = np.linalg.cholesky(corr)

    @staticmethod
    def _pairwise_correlation(t1: str, t2: str) -> float:
        tech, finance = CORRELATION_GROUPS["tech"], CORRELATION_GROUPS["finance"]
        if t1 == "TSLA" or t2 == "TSLA":
            return TSLA_CORR
        if t1 in tech and t2 in tech:
            return INTRA_TECH_CORR
        if t1 in finance and t2 in finance:
            return INTRA_FINANCE_CORR
        return CROSS_GROUP_CORR
```

## Wrapping in `MarketDataSource` — `SimulatorDataSource`

`GBMSimulator` is pure, synchronous, in-memory math with no knowledge of asyncio, the cache, or the rest of the app. `SimulatorDataSource` (in the same `simulator.py` module) adapts it to the `MarketDataSource` interface from `MARKET_INTERFACE.md`: an `asyncio.Task` loop calls `step()` every `update_interval` (default 0.5s) and writes each resulting price into the shared `PriceCache`. On `start()`, it also seeds the cache synchronously with each ticker's initial price before the loop begins, so SSE clients get data on their very first tick rather than waiting out the first interval. See `MARKET_INTERFACE.md` for the full class.

## File Structure (as built)

```
backend/
  app/
    market/
      simulator.py       # GBMSimulator + SimulatorDataSource
      seed_prices.py      # SEED_PRICES, TICKER_PARAMS, DEFAULT_PARAMS,
                           # CORRELATION_GROUPS, INTRA_TECH_CORR, INTRA_FINANCE_CORR,
                           # CROSS_GROUP_CORR, TSLA_CORR
```

`seed_prices.py` holds only constant dictionaries/sets — no logic. `simulator.py` holds both the pure-math `GBMSimulator` and the async-adapter `SimulatorDataSource`, since the two are tightly coupled (the adapter exists only to drive the simulator on a schedule) and splitting them into separate files added no real decoupling benefit during the original build.

## Behavior Notes

- Prices can never go negative — GBM's multiplicative update is `price *= exp(...)`, and `exp()` is always positive regardless of how large or negative its argument gets.
- The Cholesky decomposition is rebuilt on every `add_ticker`/`remove_ticker`, not incrementally updated. `O(n^2)` is trivial at the expected scale (watchlists of single/low-double-digit tickers).
- Random events are independent per ticker per tick — there's no correlation applied to the shock itself, only to the base GBM diffusion term. Two tickers can shock in the same tick purely by chance.
- `round(price, 2)` happens at the end of `step()`, so the simulator's internal running price retains full float precision between ticks even though only cents are ever exposed outward — rounding doesn't compound error over time the way it would if the rounded value were fed back in.
