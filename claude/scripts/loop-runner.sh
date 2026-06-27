#!/usr/bin/env bash
# Full-auto goal-loop driver. Each iteration spawns a FRESH `claude` session
# (fresh context) that does ONE next-step, verifies, and updates GOAL.md.
# Loops until GOAL.md is marked DONE, max iterations hit, or no progress (stall).
#
# This is the FULL-AUTO upgrade of the semi-auto ctx-guard loop — no human rotation.
# SAFETY: unattended. Defaults to acceptEdits (auto-accepts edits, still prompts on
# genuinely risky ops). Run in a throwaway git branch/worktree. Honors the GOAL.md
# denylist + human-gate — the agent writes a blocker and stops if it hits one.
#
# Usage:   cd <project-with-GOAL.md> && bash ~/.claude/scripts/loop-runner.sh
# Tune:    GOAL_FILE=GOAL.md MAX_ITERS=15 MAX_TURNS=40 PERM_MODE=acceptEdits  (PERM_MODE=skip = fully unattended, dangerous)
set -euo pipefail

GOAL="${GOAL_FILE:-GOAL.md}"
MAX_ITERS="${MAX_ITERS:-15}"
MAX_TURNS="${MAX_TURNS:-40}"
PERM="${PERM_MODE:-acceptEdits}"

command -v claude >/dev/null 2>&1 || { echo "claude CLI not found"; exit 1; }
[ -f "$GOAL" ] || { echo "No $GOAL here. Copy ~/.claude/templates/GOAL.md and fill it first."; exit 1; }

# safety nudge: warn if not on a non-default branch
branch="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
case "$branch" in
  main|master) echo "⚠ on '$branch' — recommend a throwaway branch/worktree for unattended runs. Ctrl-C to abort (5s)..."; sleep 5;;
esac

permflag=(--permission-mode "$PERM")
[ "$PERM" = "skip" ] && permflag=(--dangerously-skip-permissions)

PROMPT="Resume the goal in $GOAL. Read it, do ONLY the single Next step, then VERIFY it actually works (run tests/build). Update $GOAL: append a progress line, prune finished items, set the new Next step, bump Attempts N/3 + Last run. If the whole Definition-of-done is met and verified, replace the first line with 'DONE'. Honor the denylist + human-gate — if a step needs a gated/risky action, write it under a '## BLOCKED' heading in $GOAL and stop. Keep changes surgical."

prev_hash=""
for i in $(seq 1 "$MAX_ITERS"); do
  echo "──── iteration $i/$MAX_ITERS ($(date +%H:%M:%S)) ────"
  claude -p "$PROMPT" "${permflag[@]}" --max-turns "$MAX_TURNS" 2>&1 | tail -8 || { echo "claude exited non-zero — stopping"; break; }

  if head -1 "$GOAL" | grep -qiE '^#?[[:space:]]*DONE'; then echo "✅ GOAL DONE at iteration $i"; break; fi
  if grep -qiE '^##[[:space:]]*BLOCKED' "$GOAL"; then echo "⛔ hit a human-gate/blocker — stopping for review"; break; fi
  h="$(shasum "$GOAL" 2>/dev/null | awk '{print $1}')"
  if [ -n "$prev_hash" ] && [ "$h" = "$prev_hash" ]; then echo "⚠ GOAL.md unchanged this iteration — stall, stopping"; break; fi
  prev_hash="$h"
done
echo "── loop ended. Review the diff before merging. ──"
