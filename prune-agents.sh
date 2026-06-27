#!/usr/bin/env bash
# Trim ~/.claude/agents down to the curated keep-list (agents-keep.txt).
# Use after installing a full agent pack (e.g. wshobson/ECC) that re-adds ~150 unused personas.
# Moves non-kept agents to ~/.claude/agents-archive/ (reversible).
set -euo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
AG="$HOME/.claude/agents"
ARCH="$HOME/.claude/agents-archive"
[ -d "$AG" ] || { echo "no $AG"; exit 0; }
mkdir -p "$ARCH"
moved=0
while IFS= read -r f; do
  name="$(basename "$f" .md)"
  grep -qxF "$name" "$REPO/agents-keep.txt" || { mv "$f" "$ARCH/" && moved=$((moved+1)); }
done < <(find "$AG" -maxdepth 1 -name '*.md')
echo "archived $moved → $ARCH | kept $(find "$AG" -maxdepth 1 -name '*.md' | wc -l | tr -d ' ')"
