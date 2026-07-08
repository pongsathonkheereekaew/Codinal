#!/bin/bash
# backup.sh: Safely backup local machine rules and hermes configs to harness-flow repo

set -e

echo "=== Syncing Machine settings to harness-flow ==="

# 1. Backup Cursor Rules
if [ -d "$HOME/.cursor/rules" ]; then
    echo "Syncing Cursor rules..."
    mkdir -p .cursor/rules
    cp -f "$HOME/.cursor/rules"/*.mdc .cursor/rules/ 2>/dev/null || echo "No local rules found to backup."
else
    echo "No local Cursor rules folder found."
fi

# 2. Backup Hermes Soul
if [ -f "$HOME/.hermes/SOUL.md" ]; then
    echo "Syncing Hermes SOUL.md..."
    mkdir -p hermes
    cp -f "$HOME/.hermes/SOUL.md" hermes/SOUL.md
else
    echo "No local Hermes SOUL.md found."
fi

echo "=== Backup completed! Run 'git status' and commit changes ==="
