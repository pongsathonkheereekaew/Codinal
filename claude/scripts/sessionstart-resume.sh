#!/usr/bin/env bash
# SessionStart hook — resume a goal-loop.
# Clears the ctx-guard marker; injects GOAL.md + HANDOFF.md (if present in cwd) as context.
set -euo pipefail
input=$(cat)
rm -f "$HOME/.claude/.ctx-guard-fired" 2>/dev/null || true

cwd=$(printf '%s' "$input" | jq -r '.cwd // "."' 2>/dev/null || echo ".")
ctx=""
if [ -f "$cwd/GOAL.md" ]; then
  ctx="# Active GOAL (resume the loop)
$(cat "$cwd/GOAL.md")

"
fi
if [ -f "$cwd/HANDOFF.md" ]; then
  ctx="${ctx}# Last HANDOFF
$(cat "$cwd/HANDOFF.md")
"
fi
if [ -n "$ctx" ]; then
  jq -cn --arg c "$ctx" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$c}}'
fi
exit 0
