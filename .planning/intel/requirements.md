# Requirements (from PRD documents)

No documents classified as `PRD` were present in this ingest batch.

Classified docs: `PLAN.md` (SPEC), `MARKET_DATA_DESIGN.md` (SPEC), `MARKET_DATA_SUMMARY.md` (DOC), `REVIEW.md` (DOC). Product/feature requirements for FinAlly currently live inside `PLAN.md` as narrative spec sections (§2 User Experience, §8 API Endpoints, §10 Frontend Design) rather than as discrete PRD requirement entries with acceptance criteria. They have been extracted as constraints in `constraints.md` instead, tagged with their source section.

If a dedicated PRD is authored later (e.g. breaking out watchlist, trading, or chat features into separate requirement documents with acceptance criteria), re-run ingestion so `REQ-{slug}` entries are generated here. Until then, `gsd-roadmapper` should derive requirements from `constraints.md` entries sourced to `PLAN.md`.
