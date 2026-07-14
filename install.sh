#!/usr/bin/env bash
# Install Agent Harness (lingua franca + skills) → ~/.agents
# Git SSOT = this repo. Live edits to AGENTS.md are backed up then replaced.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
DEST="${AGENTS_HOME:-$HOME/.agents}"

echo "=== harness-flow → $DEST ==="
mkdir -p "$DEST"/{skills,standards,commands,scripts}

# Policy: repo wins; backup live copy if it differs
install_agents_md() {
  local src="$ROOT/AGENTS.md"
  local dest="$DEST/AGENTS.md"
  if [[ -f "$dest" ]] && ! cmp -s "$src" "$dest"; then
    local bak="$DEST/AGENTS.md.bak.$(date +%Y%m%d%H%M%S)"
    cp -f "$dest" "$bak"
    echo "WARN: live AGENTS.md differed — backed up to $bak"
  fi
  cp -f "$src" "$dest"
  echo "AGENTS.md ← repo"
}

install_agents_md

# Scripts CLI
cp -f "$ROOT"/scripts/* "$DEST/scripts/"
chmod +x "$DEST/scripts/"*
echo "scripts/ ← repo"

# Standards + commands
rsync -a --delete "$ROOT/standards/" "$DEST/standards/"
rsync -a --delete "$ROOT/commands/" "$DEST/commands/" 2>/dev/null || mkdir -p "$DEST/commands"
echo "standards/ + commands/ ← repo"

# Skills SSOT
rsync -a --delete "$ROOT/skills/" "$DEST/skills/"
echo "skills/ ← repo ($(ls -1 "$DEST/skills" | wc -l | tr -d ' ') entries)"

# Thin Claude adapter (prepend AGENTS if needed)
CLAUDE_MD="$HOME/.claude/CLAUDE.md"
if [[ -f "$CLAUDE_MD" ]]; then
  if ! grep -q 'AGENTS.md' "$CLAUDE_MD"; then
    tmp="$(mktemp)"
    { echo "# Shared policy — load first"; echo "@../.agents/AGENTS.md"; echo ""; cat "$CLAUDE_MD"; } >"$tmp"
    mv "$tmp" "$CLAUDE_MD"
    echo "prepended @AGENTS.md → ~/.claude/CLAUDE.md"
  fi
elif [[ -d "$HOME/.claude" ]]; then
  cp "$ROOT/adapters/CLAUDE.md.example" "$CLAUDE_MD"
  echo "created ~/.claude/CLAUDE.md"
fi

# Policy symlinks for other tools
link_policy() {
  local dest="$1" rel="$2"
  mkdir -p "$(dirname "$dest")"
  if [[ -L "$dest" ]] || [[ ! -e "$dest" ]]; then
    rm -f "$dest"
    ln -s "$rel" "$dest"
    echo "linked $dest"
  else
    echo "WARN keep real file: $dest"
  fi
}
link_policy "$HOME/.codex/AGENTS.md" "../.agents/AGENTS.md"
link_policy "$HOME/.zcode/AGENTS.md" "../.agents/AGENTS.md"
mkdir -p "$HOME/.config/opencode"
link_policy "$HOME/.config/opencode/AGENTS.md" "../../.agents/AGENTS.md"
mkdir -p "$HOME/.gemini"
link_policy "$HOME/.gemini/GEMINI.md" "../.agents/AGENTS.md"

# Cursor rules from standards
if [[ -x "$DEST/scripts/harness" ]]; then
  "$DEST/scripts/harness" rules || true
  "$DEST/scripts/harness" sync
fi

echo ""
echo "=== done ==="
echo "  Doctor:  $DEST/scripts/harness doctor"
echo "  Office:  optional — git clone …/agentmonitor && ./install.sh"
echo "  Edit policy in this git repo, then re-run ./install.sh (live-only edits are overwritten after backup)."
