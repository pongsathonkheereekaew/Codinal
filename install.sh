#!/usr/bin/env bash
# Install Agent Harness → ~/.agents (zero-tweak coding desk)
# Git SSOT = this repo (Codinal). Harness content lives under harness/.
# Live edits to AGENTS.md are backed up then replaced.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
HARNESS="$ROOT/harness"
DEST="${AGENTS_HOME:-$HOME/.agents}"

echo "=== Codinal → $DEST ==="
mkdir -p "$DEST"/{skills,standards,commands,scripts,memory}
mkdir -p "$HOME/.claude" "$HOME/.cursor" "$HOME/.local/bin"

# Policy: repo wins; backup live copy if it differs
install_agents_md() {
  local src="$HARNESS/AGENTS.md"
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

# Scripts CLI (recursive — carries scripts/lib + scripts/adapters Python packages)
rsync -a --delete "$HARNESS/scripts/" "$DEST/scripts/"
chmod +x "$DEST/scripts/"*
echo "scripts/ ← repo"

# Capability manifest + schema (read by harness host/verify)
rsync -a --delete "$HARNESS/config/" "$DEST/config/" 2>/dev/null || mkdir -p "$DEST/config"
rsync -a --delete "$HARNESS/schemas/" "$DEST/schemas/" 2>/dev/null || mkdir -p "$DEST/schemas"
echo "config/ + schemas/ ← repo"

# Standards + commands
rsync -a --delete "$HARNESS/standards/" "$DEST/standards/"
rsync -a --delete "$HARNESS/commands/" "$DEST/commands/" 2>/dev/null || mkdir -p "$DEST/commands"
echo "standards/ + commands/ ← repo"

# Skills SSOT
rsync -a --delete "$HARNESS/skills/" "$DEST/skills/"
echo "skills/ ← repo ($(ls -1 "$DEST/skills" | wc -l | tr -d ' ') entries)"

# Durable shared memory (not episodic)
rsync -a --delete "$HARNESS/memory/" "$DEST/memory/"
echo "memory/ ← repo ($(ls -1 "$DEST/memory" | wc -l | tr -d ' ') entries)"

# Claude durable folder → live SSOT (keep episodic engine private)
wire_claude_durable_memory() {
  local claude_home="$HOME/.claude"
  local dest_mem="$DEST/memory"
  local claude_mem="$claude_home/projects/-/memory"
  mkdir -p "$claude_home/projects/-"
  if [[ -L "$claude_mem" ]]; then
    ln -sfn "$dest_mem" "$claude_mem"
    echo "Claude memory → $dest_mem (symlink refreshed)"
  elif [[ -d "$claude_mem" ]]; then
    local bak="${claude_mem}.bak.$(date +%Y%m%d%H%M%S)"
    mv "$claude_mem" "$bak"
    ln -sfn "$dest_mem" "$claude_mem"
    echo "Claude memory → $dest_mem (old dir backed up: $bak)"
  else
    ln -sfn "$dest_mem" "$claude_mem"
    echo "Claude memory → $dest_mem (linked)"
  fi
}
wire_claude_durable_memory

# Claude adapter: create if missing; prepend @AGENTS.md if present but unwired
wire_claude_md() {
  local adapter="$HARNESS/adapters/CLAUDE.md"
  local legacy="$HARNESS/adapters/CLAUDE.md.example"
  [[ -f "$adapter" ]] || adapter="$legacy"
  local dest="$HOME/.claude/CLAUDE.md"
  mkdir -p "$HOME/.claude"
  if [[ ! -f "$dest" ]]; then
    cp -f "$adapter" "$dest"
    echo "created ~/.claude/CLAUDE.md"
  elif ! grep -q 'AGENTS.md' "$dest"; then
    local tmp
    tmp="$(mktemp)"
    { echo "# Shared policy — load first"; echo "@../.agents/AGENTS.md"; echo ""; cat "$dest"; } >"$tmp"
    mv "$tmp" "$dest"
    echo "prepended @AGENTS.md → ~/.claude/CLAUDE.md"
  else
    echo "CLAUDE.md: keep existing (already wired)"
  fi
}
wire_claude_md

# Claude plugin defaults (non-destructive merge)
if [[ -f "$HARNESS/adapters/claude-settings.defaults.json" ]]; then
  python3 "$DEST/scripts/merge-claude-settings.py" \
    "$HARNESS/adapters/claude-settings.defaults.json" \
    "$HOME/.claude/settings.json"
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

# harness on PATH (no brew/npm required)
ensure_harness_path() {
  ln -sfn "$DEST/scripts/harness" "$HOME/.local/bin/harness"
  echo "PATH: ~/.local/bin/harness → $DEST/scripts/harness"
  local line='export PATH="$HOME/.local/bin:$PATH"'
  local rc
  for rc in "$HOME/.zshrc" "$HOME/.zprofile" "$HOME/.bashrc"; do
    [[ -f "$rc" ]] || continue
    if grep -qF '.local/bin' "$rc" 2>/dev/null; then
      return 0
    fi
  done
  # Prefer zsh on macOS; create .zshrc if none of the rc files exist yet
  rc="$HOME/.zshrc"
  if [[ ! -f "$HOME/.zshrc" && ! -f "$HOME/.bashrc" && ! -f "$HOME/.zprofile" ]]; then
    touch "$rc"
  elif [[ -f "$HOME/.zshrc" ]]; then
    rc="$HOME/.zshrc"
  elif [[ -f "$HOME/.zprofile" ]]; then
    rc="$HOME/.zprofile"
  else
    rc="$HOME/.bashrc"
  fi
  {
    echo ""
    echo "# Codinal — AI Coding Desktop"
    echo "$line"
  } >>"$rc"
  echo "PATH: appended ~/.local/bin to $rc (new shells)"
}
ensure_harness_path

# Cursor rules + skill/command symlinks
if [[ -x "$DEST/scripts/harness" ]]; then
  "$DEST/scripts/harness" rules || true
  "$DEST/scripts/harness" sync
fi

echo ""
if "$DEST/scripts/harness" doctor; then
  doctor_ok=1
else
  doctor_ok=0
fi

echo ""
echo "=========================================="
if [[ "$doctor_ok" -eq 1 ]]; then
  echo " READY — open Cursor or Claude Code and work."
  echo " No extra harness tweaks required."
else
  echo " INSTALLED with warnings — run: harness doctor"
fi
echo "=========================================="
echo "  Update later:  cd ${ROOT/#$HOME/~} && git pull && ./install.sh"
echo "  Or:            harness update"
echo "  Office/Hermes: optional — see NEW_MACHINE.md"
echo ""
