# Review: Changes Since Last Commit

Reviewed working-tree changes against `d5941a0` (HEAD). Scope: `.claude/settings.json` (modified) plus untracked additions — `.claude/agents/`, `.claude/commands/`, `.claude-plugin/`, `independent-reviewer/`, `package.json`/`package-lock.json`, `README_OLD.md`, and three `planning/*.md` docs.

## 1. Critical — Three independent automations all spawn `claude -p` to write the same file, with no coordination

There are now **three separate triggers** that shell out to a fresh `claude -p` process to review the repo and write `planning/REVIEW.md`:

1. **`.claude/settings.json` — new `Stop` hook** (tracked change):
   ```json
   "Stop": [{ "hooks": [{ "type": "command",
     "command": "claude -p \"Review changes since last commit and write results to a file planning/REVIEW.md\"" }] }]
   ```
   This fires on **every Stop event of every Claude Code session in this repo** — not just after a commit, not just when the user asks for a review. It is also **not backgrounded** (no `&`/`nohup`), so it blocks the parent session's Stop handling until the nested review completes.

2. **`independent-reviewer` plugin** (new, untracked — `independent-reviewer/.claude-plugin/hooks/hooks.json` + `scripts/review-after-commit.sh`): a `PostToolUse` hook on `Bash` that fires specifically when the command contains `"git commit"`, launching `claude -p "..."` via `nohup ... & disown` (correctly backgrounded, unlike #1).

3. **`.claude/agents/change-reviewer.md`** (new, untracked): a user-/agent-invoked subagent whose entire job is to run `claude -p "..."` itself and relay the output.

All three use slightly different prompt text but the same output path. Consequences:

- **This review you're reading right now was produced by trigger #1.** The prompt that spawned this very process — *"Review changes since last commit and write results to a file planning/REVIEW.md"* — is a verbatim match for the Stop-hook command. Confirm whether `claude -p` sessions themselves fire their own `Stop` hooks; if they do, this is a **self-triggering recursive loop** with no depth guard, no dedupe, and no termination condition, and it will keep spawning nested review sessions indefinitely at real token cost.
- Even if recursion isn't an issue, trigger #1 means **every single ordinary turn** in this repo — not just commits — now blocks on a full secondary Opus session reviewing the diff. That's a significant, silent latency and cost tax on normal interactive use, for a feature (diff review) that's typically only wanted around commit time.
- Triggers #1 and #2 can race: a commit followed quickly by a session stop will fire both, each overwriting `planning/REVIEW.md` with whichever finishes last. There's no locking, no append, no distinct output per trigger.

**Recommendation:** pick one trigger (the `PostToolUse`-on-`git commit` plugin hook is the better-designed one — correctly backgrounded, scoped to actual commits) and remove the other two, or clearly separate their output files if all three are intentionally kept.

## 2. High — Two agents write to the same output file with incompatible purposes

- `.claude/agents/reviewer.md`: reviews `planning/PLAN.md` (a design-doc review) and writes to `planning/REVIEW.md`.
- `.claude/agents/change-reviewer.md`: reviews the git diff since last commit and writes to `planning/REVIEW.md`.

These do unrelated jobs but share an output path with no merge strategy — invoking either one silently clobbers the other's findings. Suggest distinct filenames (e.g. `planning/REVIEW_PLAN.md` vs `planning/REVIEW_CHANGES.md`) or folding `reviewer.md` into the `doc-review` skill/command, which already covers the PLAN.md-review use case.

## 3. Medium — Superseding docs added outside the archive, old copies left in place

`planning/MARKET_INTERFACE.md`, `MARKET_SIMULATOR.md`, and `MASSIVE_API.md` are new, untracked files at the `planning/` root. Each is a substantially rewritten version of an identically-named file already sitting in `planning/archive/` — and `MARKET_INTERFACE.md`'s own text says so explicitly: *"It supersedes `planning/archive/MARKET_INTERFACE.md`, correcting it in one place where the sketch diverged from the shipped code."*

Per `CLAUDE.md`, the archive folder is documented as the home for market-data detail docs, and `MARKET_DATA_SUMMARY.md` is the canonical summary. Right now there are two versions of each doc in two locations with no cross-reference, and it's not clear whether:
- the new root-level copies should replace the archive copies (via `git mv` + content update, so history is preserved), or
- they're meant to live alongside the archive as corrected standalone docs, with the archive explicitly marked stale.

As-is, a future reader hitting `planning/archive/MARKET_INTERFACE.md` will get the superseded, less-accurate version with no pointer to the corrected one at `planning/MARKET_INTERFACE.md`. Recommend resolving this explicitly — most likely, move the corrected versions into `archive/` (overwriting) and deleting the stray root copies, consistent with the directory structure in `PLAN.md` §4.

## 4. Low — Stray/unexplained files

- **`package.json` is `{}`** (plus a generated `package-lock.json`). No `name`, `version`, or `dependencies`. Given the project's actual frontend lives in `frontend/` as its own Next.js project (per `PLAN.md` §4), a root-level empty `package.json` looks like a stray artifact from running `npm install` outside any project context. If unintentional, delete both; if intentional (e.g. for a root-level tool), it needs at least a `name` and a comment on purpose.
- **`README_OLD.md`** — appears to be an intentional pre-commit backup of the previous README, superseded by the current `README.md`'s "Status" table (commit `d5941a0`). Not a problem, but if it's not meant to be committed, it should be removed or added to `.gitignore` rather than left untracked indefinitely.

## Not reviewed

A large number of additional untracked paths (`.bashrc`, `.zshrc`, `.gitconfig`, `.idea/`, `.vscode/`, `.mcp.json`, `.claude/hooks`, `.claude/workflows`, etc.) appeared in `git status` during this review but resolve to character-device files (major/minor `1,3`, i.e. `/dev/null`-equivalents) owned by `nobody:nogroup`, not real content — these are sandbox/session artifacts, not repository changes, and are excluded from this review.
