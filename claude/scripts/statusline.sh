#!/usr/bin/env bash
# ~/.claude/statusline.sh
# Claude Code status line — single output line, fields separated by " | "

input=$(cat)

# ── 1. Model name ────────────────────────────────────────────────────────────
model=$(echo "$input" | jq -r '.model.display_name // "Unknown model"')

# ── 2. Context usage % ───────────────────────────────────────────────────────
# tokens_used = input_tokens + cache_read + cache_creation (from current_usage)
# context_window_size comes from the payload; fall back to 200000
ctx_size=$(echo "$input" | jq -r '.context_window.context_window_size // 200000')
cur=$(echo "$input" | jq -r '.context_window.current_usage // empty')
if [ -n "$cur" ]; then
  tokens_used=$(echo "$input" | jq -r '
    (.context_window.current_usage.input_tokens // 0)
    + (.context_window.current_usage.cache_read_input_tokens // 0)
    + (.context_window.current_usage.cache_creation_input_tokens // 0)
  ')
  ctx_pct=$(echo "$tokens_used $ctx_size" | awk '{printf "%.0f", ($1/$2)*100}')
else
  # Fall back to pre-calculated field
  ctx_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
  [ -z "$ctx_pct" ] && ctx_pct="0"
  ctx_pct=$(printf "%.0f" "$ctx_pct")
  tokens_used=$(echo "$input" | jq -r '
    (.context_window.total_input_tokens // 0)
    + (.context_window.total_output_tokens // 0)
  ')
fi
context_field="${ctx_pct}% context"

# ── 3. Total tokens used this session ────────────────────────────────────────
total_in=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
total_out=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')
total_tokens=$((total_in + total_out))
# Format with thousands separator
token_field=$(printf "%'d tokens" "$total_tokens")

# ── 4 & 5. Rate limits (5-hour and weekly) ───────────────────────────────────
five_pct=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
five_reset=$(echo "$input" | jq -r '.rate_limits.five_hour.resets_at // empty')
week_pct=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
week_reset=$(echo "$input" | jq -r '.rate_limits.seven_day.resets_at // empty')

# Format 5-hour field
if [ -n "$five_pct" ] && [ -n "$five_reset" ]; then
  five_pct_fmt=$(printf "%.0f" "$five_pct")
  five_time=$(date -r "$five_reset" "+%H:%M" 2>/dev/null || date -d "@$five_reset" "+%H:%M" 2>/dev/null || echo "?")
  daily_field="Daily usage ${five_pct_fmt}% reset at ${five_time}"
else
  daily_field="Daily usage —"
fi

# Format weekly field
if [ -n "$week_pct" ] && [ -n "$week_reset" ]; then
  week_pct_fmt=$(printf "%.0f" "$week_pct")
  # "3 May 10:00am" format
  week_day=$(date -r "$week_reset" "+%-d %b" 2>/dev/null || date -d "@$week_reset" "+%-d %b" 2>/dev/null || echo "?")
  week_time=$(date -r "$week_reset" "+%I:%M%p" 2>/dev/null || date -d "@$week_reset" "+%I:%M%p" 2>/dev/null || echo "?")
  # lowercase am/pm and strip leading zero from hour
  week_time=$(echo "$week_time" | tr '[:upper:]' '[:lower:]' | sed 's/^0//')
  weekly_field="Weekly usage ${week_pct_fmt}% reset at ${week_day} ${week_time}"
else
  weekly_field="Weekly usage —"
fi

# ── 6. Timestamp of last user message from transcript ────────────────────────
transcript=$(echo "$input" | jq -r '.transcript_path // empty')
last_ts_field="—"
if [ -n "$transcript" ] && [ -f "$transcript" ]; then
  # JSONL: find last line with role=="user", extract timestamp
  last_ts=$(grep -o '"role":"user"[^}]*"timestamp":"[^"]*"' "$transcript" 2>/dev/null | tail -1 | grep -o '"timestamp":"[^"]*"' | sed 's/"timestamp":"//;s/"//')
  if [ -z "$last_ts" ]; then
    # Try alternate JSONL structure where timestamp is a top-level key
    last_ts=$(grep '"role":"user"' "$transcript" 2>/dev/null | tail -1 | jq -r '.timestamp // empty' 2>/dev/null)
  fi
  if [ -n "$last_ts" ]; then
    # Parse ISO8601 and reformat as HH:MM:SS
    if [[ "$last_ts" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T([0-9]{2}:[0-9]{2}:[0-9]{2}) ]]; then
      last_ts_field="${BASH_REMATCH[1]}"
    else
      last_ts_field="$last_ts"
    fi
  fi
fi

# ── Assemble ─────────────────────────────────────────────────────────────────
echo "${model} | ${context_field} | ${token_field} | ${daily_field} | ${weekly_field} | ${last_ts_field}"
