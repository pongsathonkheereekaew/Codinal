#!/bin/bash
# Pull live Agent Harness state into this repo before commit
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== backup ~/.agents → harness-flow ==="

if [ -d "$HOME/.agents/skills" ]; then
  rsync -a --delete "$HOME/.agents/skills/" "$ROOT/skills/"
  echo "skills/"
fi
if [ -f "$HOME/.agents/AGENTS.md" ]; then
  cp -f "$HOME/.agents/AGENTS.md" "$ROOT/AGENTS.md"
  echo "AGENTS.md"
fi
if [ -d "$HOME/.agents/standards" ]; then
  rsync -a "$HOME/.agents/standards/" "$ROOT/standards/"
  echo "standards/"
fi
if [ -d "$HOME/.agents/commands" ]; then
  rsync -a "$HOME/.agents/commands/" "$ROOT/commands/"
  echo "commands/"
fi
if [ -d "$HOME/.agents/memory" ]; then
  mkdir -p "$ROOT/memory"
  rsync -a "$HOME/.agents/memory/" "$ROOT/memory/"
  echo "memory/"
fi
if [ -d "$HOME/.cursor/rules" ]; then
  mkdir -p .cursor/rules
  cp -f "$HOME/.cursor/rules"/*.mdc .cursor/rules/ 2>/dev/null || true
  echo ".cursor/rules/"
fi

echo "=== done. Review git status (no secrets). ==="
echo "Hermes/SOUL lives in the agentmonitor repo — not backed up here."
