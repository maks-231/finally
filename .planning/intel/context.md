# Context (from DOC documents)

Two documents classified as `DOC`: `planning/MARKET_DATA_SUMMARY.md` and `planning/REVIEW.md`. DOC is the lowest-precedence tier by default; where either overlaps with SPEC content it is deferred to (see `constraints.md` and `INGEST-CONFLICTS.md`).

---

## Topic: Market data subsystem status & module overview
- **source**: planning/MARKET_DATA_SUMMARY.md
- Status: "Complete, tested, reviewed, all issues resolved." A complete market data subsystem in `backend/app/market/` (8 modules) providing live price simulation and real market data via a unified interface. Module table: `models.py` (`PriceUpdate` immutable frozen dataclass), `interface.py` (`MarketDataSource` ABC), `cache.py` (`PriceCache`), `seed_prices.py` (seed prices, GBM params, correlation groups), `simulator.py` (`GBMSimulator` + `SimulatorDataSource`), `massive_client.py` (`MassiveDataSource`), `factory.py` (`create_market_data_source()`), `stream.py` (`create_stream_router()`).
- Note: this document states the module set is "~500 lines"; `MARKET_DATA_DESIGN.md` (SPEC, higher precedence) states "~770 lines" for the same module set. Per precedence rules, SPEC's figure is treated as authoritative — see auto-resolved entry in `INGEST-CONFLICTS.md`.

## Topic: Key design decisions (summary-level)
- **source**: planning/MARKET_DATA_SUMMARY.md
- Strategy pattern (both sources implement the same ABC, downstream code is source-agnostic); `PriceCache` as single point of truth (producers write, consumers read, no direct coupling); GBM with correlated moves (Cholesky decomposition, tech 0.6 / finance 0.5 / cross-sector 0.3 — consistent with the fuller parameter set in `constraints.md` #4 from `MARKET_DATA_DESIGN.md`); random shock events (~0.1% chance per tick per ticker, 2-5% move); SSE over WebSockets (simplicity, one-way push, universal browser support).

## Topic: Test suite results
- **source**: planning/MARKET_DATA_SUMMARY.md
- 73 tests, all passing, 84% overall coverage, 6 test modules under `backend/tests/market/` — figures match `MARKET_DATA_DESIGN.md` §10 exactly (test_models.py 11/100%, test_cache.py 13/100%, test_simulator.py 17/98%, test_simulator_source.py 10 integration, test_factory.py 7/100%, test_massive.py 13/56% "expected — API methods mocked").

## Topic: Code review fixes applied
- **source**: planning/MARKET_DATA_SUMMARY.md
- A prior code review identified 7 issues, all resolved: (1) `pyproject.toml` build config missing `[tool.hatch.build.targets.wheel] packages = ["app"]`; (2) lazy imports of `massive` removed, moved to top-level since it's a core dependency; (3) SSE return type annotated as `AsyncGenerator[str, None]`; (4) public `get_tickers()` added to `GBMSimulator` to avoid private attribute access; (5) correlation constants cleaned up (removed unused `DEFAULT_CORR`, consolidated into `CROSS_GROUP_CORR`); (6) unused test imports (`pytest`, `math`, `asyncio`) removed from 4 test files; (7) Massive test mocks fixed (`source._client` set in tests, patches target correct names).

## Topic: Demo & usage for downstream code
- **source**: planning/MARKET_DATA_SUMMARY.md
- Rich terminal demo at `backend/market_data_demo.py` (`cd backend && uv run market_data_demo.py`) — live dashboard, all 10 tickers, sparklines, color-coded direction arrows, event log for shocks, runs 60s or until Ctrl+C. Downstream usage snippet: construct `PriceCache()`, `create_market_data_source(cache)`, `await source.start([...])`; read via `cache.get(ticker)` / `cache.get_price(ticker)` / `cache.get_all()`; mutate watchlist via `source.add_ticker`/`remove_ticker`; `await source.stop()` on shutdown.

---

## Topic: Automation/hook coordination risk
- **source**: planning/REVIEW.md §1
- Three independent, uncoordinated automations all shell out to `claude -p` and write the same `planning/REVIEW.md`: (1) a `.claude/settings.json` `Stop` hook firing on every session Stop (not just after commits), not backgrounded, blocking the parent session; (2) the `independent-reviewer` plugin's `PostToolUse`-on-`git commit` hook, correctly backgrounded via `nohup ... & disown`; (3) the `.claude/agents/change-reviewer.md` subagent, user/agent-invoked. Flags a possible self-triggering recursive loop (if nested `claude -p` sessions fire their own Stop hooks, with no depth guard/dedupe/termination condition) and a race condition where concurrent triggers overwrite each other's output with no locking or append semantics. Recommends keeping only the `PostToolUse`-on-commit plugin hook and removing the other two, or giving each trigger a distinct output file.

## Topic: Shared-output-file collision between review agents
- **source**: planning/REVIEW.md §2
- `.claude/agents/reviewer.md` (design-doc review of `planning/PLAN.md`) and `.claude/agents/change-reviewer.md` (git-diff review) both write to `planning/REVIEW.md` with no merge strategy — invoking either silently clobbers the other's findings. Suggested fix: distinct filenames (e.g. `REVIEW_PLAN.md` vs `REVIEW_CHANGES.md`) or folding `reviewer.md` into an existing `doc-review` skill/command.

## Topic: Superseding market-data docs duplicated outside archive
- **source**: planning/REVIEW.md §3
- `planning/MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, and `MASSIVE_API.md` are new, untracked root-level files, each a substantial rewrite of an identically-named file already in `planning/archive/`; `MARKET_INTERFACE.md`'s own text says it supersedes the archived version. Per `CLAUDE.md`, the archive folder is documented as home for market-data detail docs with `MARKET_DATA_SUMMARY.md` as canonical summary — so two versions of each doc now exist in two locations with no cross-reference, and it is unresolved whether the root copies should replace the archive copies (via `git mv` + content update) or coexist with the archive explicitly marked stale. None of these three files were present in this ingest batch, so this synthesis could not independently verify or reconcile their content — flagged here for downstream awareness only.

## Topic: Stray/unexplained files
- **source**: planning/REVIEW.md §4
- Root-level `package.json` is `{}` (no name/version/dependencies) plus a generated `package-lock.json` — looks like a stray artifact from running `npm install` outside any project context, given the real frontend lives in `frontend/` as its own Next.js project per `PLAN.md` §4. `README_OLD.md` appears to be an intentional pre-commit backup of the previous README, superseded by the current `README.md`; flagged as something that should be removed or gitignored if not meant to be committed long-term.
