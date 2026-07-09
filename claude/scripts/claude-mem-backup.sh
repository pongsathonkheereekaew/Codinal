#!/usr/bin/env bash
# SessionStart hook — weekly claude-mem DB backup, COMPRESSED (sqlite .backup + gzip).
# Consistent snapshot of the live DB, ~5-10x smaller than a raw copy. Keeps newest 4.
set -euo pipefail
input=$(cat); : "$input"   # consume hook stdin, ignore

db="$HOME/.claude-mem/claude-mem.db"
bdir="$HOME/.claude-mem/backups"
[ -f "$db" ] || exit 0
mkdir -p "$bdir"

latest="$(ls -t "$bdir"/weekly-*.db.gz 2>/dev/null | head -1 || true)"
if [ -z "$latest" ] || find "$latest" -mtime +7 2>/dev/null | grep -q .; then
  out="$bdir/weekly-$(date +%Y%m%d).db"
  if command -v sqlite3 >/dev/null 2>&1; then
    sqlite3 "$db" ".backup '$out'" 2>/dev/null || cp "$db" "$out"
  else
    cp "$db" "$out"
  fi
  gzip -f "$out" 2>/dev/null || rm -f "$out"
  # keep newest 4, drop older + any legacy uncompressed snapshots
  ls -t "$bdir"/weekly-*.db.gz 2>/dev/null | tail -n +5 | while read -r f; do rm -f "$f"; done
  rm -f "$bdir"/weekly-*.db 2>/dev/null || true
fi
exit 0
