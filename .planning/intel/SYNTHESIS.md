# Synthesis Summary

Entry point for `gsd-roadmapper`. Mode: `new`. Precedence used: default `ADR > SPEC > PRD > DOC` (no per-doc overrides present).

## Docs synthesized: 4

| Type | Count | Source paths |
|---|---|---|
| ADR | 0 | — |
| SPEC | 2 | planning/PLAN.md, planning/MARKET_DATA_DESIGN.md |
| PRD | 0 | — |
| DOC | 2 | planning/MARKET_DATA_SUMMARY.md, planning/REVIEW.md |

All 4 classifications had `confidence: high` — no UNKNOWN/low-confidence docs to flag.

## Decisions locked: 0
No ADR-type documents in this batch. See `.planning/intel/decisions.md`.

## Requirements extracted: 0
No PRD-type documents in this batch. Feature/UX requirements for FinAlly currently live as narrative SPEC content inside `planning/PLAN.md` and have been captured as constraints instead (see below). See `.planning/intel/requirements.md`.

## Constraints: 18
Extracted from the 2 SPEC documents. Type breakdown: `schema` 1, `api-contract` 3, `protocol` 6, `nfr` 8. See `.planning/intel/constraints.md`. Covers: single-container architecture, tech stack rationale, env var behavior, DB schema, trade execution rules, REST+SSE API surface, LLM integration/structured-output schema, frontend UI requirements, Docker/deployment, testing strategy (all from PLAN.md); MarketDataSource interface, PriceCache/threading, provider factory, GBM simulator math, SSE streaming implementation, Massive API integration (with a self-flagged field-mapping risk), market data lifecycle, market data test coverage (all from MARKET_DATA_DESIGN.md).

## Context topics: 9
Extracted from the 2 DOC documents. See `.planning/intel/context.md`. Covers: market-data status/modules, design-decision summary, test results, code-review fixes applied, demo/usage (from MARKET_DATA_SUMMARY.md); automation/hook coordination risk, shared-output-file collision between review agents, duplicated market-data topic docs outside archive, stray files (from REVIEW.md).

## Conflicts: 0 blockers, 0 competing-variants, 2 auto-resolved (INFO)
- No cross-ref cycles; no LOCKED decisions in play; no PRD acceptance-criteria overlaps possible (no PRDs).
- 1 auto-resolved factual discrepancy: SPEC (~770 lines) wins over DOC (~500 lines) for market-data module size.
- 1 non-blocking self-reported risk noted (Massive API timestamp field-mapping, flagged by the SPEC itself, not a cross-doc conflict).
- Full detail: `.planning/INGEST-CONFLICTS.md`

## Pointers
- Per-type intel: `.planning/intel/decisions.md`, `.planning/intel/requirements.md`, `.planning/intel/constraints.md`, `.planning/intel/context.md`
- Conflicts report: `.planning/INGEST-CONFLICTS.md`
