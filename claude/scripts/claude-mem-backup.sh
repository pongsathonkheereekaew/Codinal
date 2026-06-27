#!/usr/bin/env bash
# SessionStart hook — weekly claude-mem DB backup (portable, no cron). Keeps newest 4.
set -euo pipefail
input=$(cat); : "$input"   # consume hook stdin, ignore

db="$HOME/.claude-mem/claude-mem.db"
bdir="$HOME/.claude-mem/backups"
[ -f "$db" ] || exit 0
mkdir -p "$bdir"

latest="$(ls -t "$bdir"/weekly-*.db 2>/dev/null | head -1 || true)"
if [ -z "$latest" ] || find "$latest" -mtime +7 2>/dev/null | grep -q .; then
  cp "$db" "$bdir/weekly-$(date +%Y%m%d).db" 2>/dev/null || true
  ls -t "$bdir"/weekly-*.db 2>/dev/null | tail -n +5 | while read -r f; do rm -f "$f"; done
fi
exit 0
