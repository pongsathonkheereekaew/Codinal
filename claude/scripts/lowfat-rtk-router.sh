#!/usr/bin/env bash
# Routes Claude Code PreToolUse Bash hook:
#   git/grep/find/ls/tree/docker -> lowfat (higher compression on these)
#   everything else              -> rtk  (broad coverage incl. cmake)
set -euo pipefail

input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // ""')

# Strip env-var prefixes (FOO=bar BAZ=qux git log ...) and leading sudo
stripped=$(printf '%s' "$cmd" | awk '
{
  i=1
  while (i<=NF && $i ~ /^[A-Za-z_][A-Za-z0-9_]*=/) i++
  if (i<=NF && $i=="sudo") i++
  print $i
}')
first=$(basename "${stripped:-}")

case "$first" in
  git|grep|find|ls|tree|docker)
    exec lowfat hook <<<"$input"
    ;;
  *)
    exec rtk hook claude <<<"$input"
    ;;
esac
