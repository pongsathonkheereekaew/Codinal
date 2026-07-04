#!/usr/bin/env bash
# SessionStart hook — resume a goal-loop.
# Clears the ctx-guard marker; injects TASK_BRIEF.md + GOAL.md + HANDOFF.md (if present in cwd).
# TASK_BRIEF is first so the original ask is never lost behind progress notes.
set -euo pipefail
input=$(cat)
rm -f "$HOME/.claude/.ctx-guard-fired" 2>/dev/null || true

cwd=$(printf '%s' "$input" | jq -r '.cwd // "."' 2>/dev/null || echo ".")
ctx=""

if [ -f "$cwd/TASK_BRIEF.md" ]; then
  ctx="# ORIGINAL TASK BRIEF (resume this — do not restart from scratch)
$(cat "$cwd/TASK_BRIEF.md")

"
fi
if [ -f "$cwd/GOAL.md" ]; then
  ctx="${ctx}# Active GOAL (resume the loop)
$(cat "$cwd/GOAL.md")

"
fi
if [ -f "$cwd/HANDOFF.md" ]; then
  ctx="${ctx}# Last HANDOFF
$(cat "$cwd/HANDOFF.md")
"
fi

if [ -n "$ctx" ]; then
  ctx="${ctx}
# Resume instructions
Continue the ORIGINAL TASK BRIEF above. Do not ask the user to restate it. Run autonomously and self-verify. Translate to Thai only if the user asks. If a plugin binary is involved, use /br before measure/audit.
"
  jq -cn --arg c "$ctx" '{hookSpecificOutput:{hookEventName:"SessionStart",additionalContext:$c}}'
fi
exit 0
