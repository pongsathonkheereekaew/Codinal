#!/usr/bin/env bash
# Stop hook — auto-handoff guard for goal-loops.
# The Stop-hook payload has NO context_window field (verified), but it does carry
# transcript_path. So we read the transcript's recent cumulative token usage
# (input + cache_read + cache_creation = current context size) and fire at a
# token threshold. Default 800000 (~80% of glm-5.2[1m]'s 1M window).
# Override per-machine/model with env CTX_GUARD_TOKENS (e.g. 160000 for a 200K model).
# Fires when ARMED (GOAL.md / HANDOFF.md / TASK_BRIEF.md in cwd OR ~/.claude/.loop-active), once per session.
# On fire: also writes TASK_BRIEF.md from the first real user message so resume keeps the original ask.
set -euo pipefail
input=$(cat)

cwd=$(printf '%s' "$input" | jq -r '.cwd // "."' 2>/dev/null || echo ".")
# gate: only act when a loop is armed (goal, handoff, brief, or explicit arm file)
if [ ! -f "$cwd/GOAL.md" ] && [ ! -f "$cwd/HANDOFF.md" ] && [ ! -f "$cwd/TASK_BRIEF.md" ] && [ ! -f "$HOME/.claude/.loop-active" ]; then
  exit 0
fi

tp=$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2>/dev/null || true)
[ -n "$tp" ] && [ -f "$tp" ] || exit 0

# current context size = peak cumulative usage over the recent transcript tail
used=$(tail -150 "$tp" 2>/dev/null | jq -rs '
  map(select(.message.usage))
  | map((.message.usage.input_tokens//0)+(.message.usage.cache_read_input_tokens//0)+(.message.usage.cache_creation_input_tokens//0))
  | (max // 0)' 2>/dev/null || echo 0)
[ -n "$used" ] || used=0

threshold="${CTX_GUARD_TOKENS:-800000}"
marker="$HOME/.claude/.ctx-guard-fired"

if [ "${used:-0}" -ge "$threshold" ] && [ ! -f "$marker" ]; then
  touch "$marker"
  pct=$(( used * 100 / 1000000 ))

  # Capture original user brief so the next session does not restart cold
  if [ ! -f "$cwd/TASK_BRIEF.md" ] || [ ! -s "$cwd/TASK_BRIEF.md" ]; then
    brief=$(jq -r '
      select(.type=="user")
      | .message.content
      | if type=="string" then .
        elif type=="array" then ([.[] | select(.type=="text") | .text] | join("\n"))
        else empty end
      ' "$tp" 2>/dev/null | grep -v '^[[:space:]]*$' | grep -viE '^(Continue|Retry|ok|go|แปล|done\??)$' | head -1 || true)
    if [ -n "${brief:-}" ]; then
      {
        echo "# TASK_BRIEF (auto-captured at context limit)"
        echo
        echo "$brief"
      } > "$cwd/TASK_BRIEF.md"
    fi
  fi

  printf '{"decision":"block","reason":"CONTEXT ~%s tokens (>= %s threshold, ~%s%% of 1M). Before stopping: (1) ensure TASK_BRIEF.md has the ORIGINAL user ask (create/update if missing), (2) update GOAL.md — append progress + the single next step, PRUNE finished items, bump Attempts N/3 + Last run, (3) run the handoff skill to write HANDOFF.md (redact secrets; include the task brief at the top), (4) tell the user: open a fresh session and type continue. Do this now, then stop."}' "$used" "$threshold" "$pct"
  exit 0
fi
exit 0
