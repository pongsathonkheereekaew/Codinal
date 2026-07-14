#!/bin/bash
# install.sh: Machine install for harness-flow
# 1) Agent Harness → ~/.agents  2) Cursor rules  3) Claude packs  4) Hermes kit

set -e

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== Starting harness-flow installation ==="

# 0. Agent Harness (lingua franca + scripts) — never overwrites existing AGENTS.md
echo "0. Installing Agent Harness → ~/.agents ..."
if [ -f templates/agents-harness/install.sh ]; then
    bash templates/agents-harness/install.sh
else
    echo "   ⚠ templates/agents-harness missing — skip"
fi

# 1. Cursor rules snapshot (prefer regenerating from ~/.agents/standards later)
echo "1. Installing Cursor rules snapshot..."
mkdir -p ~/.cursor/rules
cp -f .cursor/rules/*.mdc ~/.cursor/rules/ 2>/dev/null || echo "   No .cursor/rules snapshots; use: ~/.agents/scripts/harness rules"

# 2. Claude Code workflow (skills, agents, hooks)
echo "2. Installing Claude Code workflow..."
if [ -d "claude/skills" ]; then
    bash scripts/install-claude.sh
else
    echo "   ⚠ claude/skills missing — restore from git history if needed"
fi

# 3. Hermes kit files (review SOUL.md; do not treat as second AGENTS.md)
echo "3. Setting up Hermes Agent configuration..."
mkdir -p ~/.hermes
if [ -d "hermes" ]; then
    # copy helpers; keep live config.yaml/.env if already present
    for f in SOUL.md README.md doctor.sh restart-gateway.sh apply-fix.sh install.sh; do
        [ -f "hermes/$f" ] && cp -f "hermes/$f" ~/.hermes/
    done
    mkdir -p ~/.hermes/bin ~/.hermes/LaunchAgents
    cp -f hermes/bin/* ~/.hermes/bin/ 2>/dev/null || true
    cp -f hermes/LaunchAgents/* ~/.hermes/LaunchAgents/ 2>/dev/null || true
    if [ ! -f ~/.hermes/config.yaml ] && [ -f hermes/config.yaml ]; then
        cp -f hermes/config.yaml ~/.hermes/config.yaml
    fi
    echo "   Hermes kit copied (existing config.yaml preserved if present)."
    echo "   Ensure skills.external_dirs includes ~/.agents/skills — see templates/agents-harness/adapters/"
else
    echo "   No hermes/ directory found."
fi

echo "=== Installation completed ==="
echo "Next:"
echo "  1. ~/.agents/scripts/harness sync && harness doctor"
echo "  2. Follow NEW_MACHINE.md for 9router / Telegram / projects"
echo "  3. bash ./verify.sh"
