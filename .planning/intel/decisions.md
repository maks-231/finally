# Decisions (from ADR documents)

No documents classified as `ADR` were present in this ingest batch.

Classified docs: `PLAN.md` (SPEC), `MARKET_DATA_DESIGN.md` (SPEC), `MARKET_DATA_SUMMARY.md` (DOC), `REVIEW.md` (DOC). None carry `locked: true` or ADR type, so there are no LOCKED decisions to enforce from this batch and no ADR-vs-ADR precedence conflicts are possible.

Architectural choices that would typically live in an ADR appear instead inside the SPEC documents (see `constraints.md`) as rationale tables — e.g. PLAN.md §3 "Why These Choices" (SSE over WebSockets, static Next.js export, SQLite over Postgres, single Docker container, uv for Python, market-orders-only). These are recorded as constraints, not decisions, because their source documents are typed SPEC, not ADR. If the project later formalizes these as ADRs, re-run ingestion so they are captured here with LOCKED status where applicable.
