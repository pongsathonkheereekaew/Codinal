#!/bin/bash
# Pull live Agent Harness state into this repo before commit
# Codinal layout: harness content under harness/, product at root.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
HARNESS="$ROOT/harness"
cd "$ROOT"

echo "=== backup ~/.agents → harness-flow/harness ==="

if [ -d "$HOME/.agents/skills" ]; then
  rsync -a --delete "$HOME/.agents/skills/" "$HARNESS/skills/"
  echo "skills/"
fi
if [ -f "$HOME/.agents/AGENTS.md" ]; then
  cp -f "$HOME/.agents/AGENTS.md" "$HARNESS/AGENTS.md"
  echo "AGENTS.md"
fi
if [ -d "$HOME/.agents/standards" ]; then
  rsync -a "$HOME/.agents/standards/" "$HARNESS/standards/"
  echo "standards/"
fi
if [ -d "$HOME/.agents/commands" ]; then
  rsync -a "$HOME/.agents/commands/" "$HARNESS/commands/"
  echo "commands/"
fi
if [ -d "$HOME/.agents/memory" ]; then
  mkdir -p "$HARNESS/memory"
  rsync -a "$HOME/.agents/memory/" "$HARNESS/memory/"
  echo "memory/"
fi
if [ -d "$HOME/.cursor/rules" ]; then
  mkdir -p .cursor/rules
  cp -f "$HOME/.cursor/rules"/*.mdc .cursor/rules/ 2>/dev/null || true
  echo ".cursor/rules/"
fi

echo "=== done. Review git status (no secrets). ==="
echo "Hermes/SOUL lives in the agentmonitor repo — not backed up here."
