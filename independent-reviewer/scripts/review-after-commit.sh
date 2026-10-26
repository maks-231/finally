#!/usr/bin/env bash
set -euo pipefail

input="$(cat)"
command="$(jq -r '.tool_input.command // empty' <<<"$input")"

[[ "$command" == *"git commit"* ]] || exit 0

cwd="$(jq -r '.cwd // empty' <<<"$input")"
[[ -n "$cwd" ]] && cd "$cwd"

nohup claude -p "Please do a comprehensive review of all changes since the last commit in this repository. Check them for internal inconsistencies, ambiguities, missing specification, and simplification opportunities. Write your feedback to planning/REVIEW.md." >/dev/null 2>&1 &
disown

exit 0
