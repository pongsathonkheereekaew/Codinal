#!/bin/bash
# backup.sh: pull live machine settings into harness-flow before commit
set -e

echo "=== Syncing machine settings → harness-flow ==="

# 1. Cursor rules snapshot
if [ -d "$HOME/.cursor/rules" ]; then
    echo "Syncing Cursor rules..."
    mkdir -p .cursor/rules
    cp -f "$HOME/.cursor/rules"/*.mdc .cursor/rules/ 2>/dev/null || echo "No local rules found."
else
    echo "No local Cursor rules folder."
fi

# 2. Hermes SOUL (keep thin — do not dump AGENTS.md here)
if [ -f "$HOME/.hermes/SOUL.md" ]; then
    echo "Syncing Hermes SOUL.md..."
    mkdir -p hermes
    cp -f "$HOME/.hermes/SOUL.md" hermes/SOUL.md
else
    echo "No local Hermes SOUL.md."
fi

echo "=== Backup done. Review git status (do not commit secrets). ==="
echo "Tip: live policy/skills stay in ~/.agents — not copied by this script."
