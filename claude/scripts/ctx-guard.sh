#!/usr/bin/env bash
# Stop hook — auto-handoff guard.
# Fires only in goal-loop mode (GOAL.md in cwd OR ~/.claude/.loop-active).
# At >=80% context: force handoff once, then allow stop. SessionStart clears the marker.
set -euo pipefail
input=$(cat)
# TEMP debug: capture Stop-hook payload once to verify .context_window is present (remove after verified)
printf '%s\n' "$input" >> "$HOME/.claude/.ctx-guard-debug.log" 2>/dev/null || true

cwd=$(printf '%s' "$input" | jq -r '.cwd // "."' 2>/dev/null || echo ".")
# gate: only act when a loop is armed
if [ ! -f "$cwd/GOAL.md" ] && [ ! -f "$HOME/.claude/.loop-active" ]; then
  exit 0
fi

pct=$(printf '%s' "$input" | jq -r '(.context_window.used_percentage // 0)' 2>/dev/null | cut -d. -f1)
marker="$HOME/.claude/.ctx-guard-fired"

if [ "${pct:-0}" -ge 80 ] && [ ! -f "$marker" ]; then
  touch "$marker"
  printf '{"decision":"block","reason":"CONTEXT %s%% >= 80%%. Before stopping: (1) update GOAL.md — append progress + the single next step, PRUNE finished items, bump Attempts N/3 + Last run, (2) run the handoff skill to write HANDOFF.md (redact secrets), (3) tell the user: open a fresh session and type continue. Do this now, then stop."}' "$pct"
  exit 0
fi
exit 0
