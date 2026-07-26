#!/bin/bash
# easby-agent setup — install the suite's commands + agents into ~/.claude as symlinks
# (single source of truth = this repo). Skills already live here at ~/.claude/skills/easby/.
# Idempotent. Non-symlink originals are backed up to *.pre-easby.bak.
set -e
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

link() { # $1 = path in repo, $2 = target in ~/.claude
  local src="$REPO/$1" dst="$2"
  [ -e "$dst" ] && [ ! -L "$dst" ] && { mv "$dst" "$dst.pre-easby.bak"; echo "  backed up $dst → $dst.pre-easby.bak"; }
  ln -sfn "$src" "$dst"
  echo "  linked $dst → $1"
}

mkdir -p "$HOME/.claude/commands" "$HOME/.claude/agents"
echo "Installing easby commands:"
for c in produce mix master decomp easby-programming; do link "commands/$c.md" "$HOME/.claude/commands/$c.md"; done
echo "Installing easby agents:"
link "agents/easby-programmer.md" "$HOME/.claude/agents/easby-programmer.md"

echo
echo "Done. Skills load from ~/.claude/skills/easby/ (this repo). Router: shared/INDEX.md (full music KB)."
echo "Research workspace (RE harnesses + REF) lives in the separate private repo: easby-research."

# Plugin manuals (Obsidian vault, iCloud-synced) — link if present on this machine
VAULT="$HOME/Library/Mobile Documents/iCloud~md~obsidian/Documents/Easby Studios/Plug-Ins"
if [ -d "$VAULT" ]; then ln -sfn "$VAULT" "$REPO/shared/plugins/manuals/vault"; echo "linked plugin manuals → vault"; else echo "(plugin manuals vault not found — skip; cards still work)"; fi
