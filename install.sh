#!/usr/bin/env bash
# Install this Claude Code workflow into ~/.claude on a fresh machine.
# Idempotent: backs up anything it overwrites to *.bak-<timestamp>.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SRC="$REPO/claude"
DEST="$HOME/.claude"
TS="$(date +%Y%m%d-%H%M%S)"

echo "==> Installing Claude Code workflow into $DEST"
mkdir -p "$DEST"/{scripts,commands,templates,agents,skills} "$DEST/projects/-/memory"

backup() { [ -e "$1" ] && cp -a "$1" "$1.bak-$TS" && echo "   backed up $(basename "$1")" || true; }

# 1. core dotfiles (backup existing first)
backup "$DEST/CLAUDE.md";    cp "$SRC/CLAUDE.md" "$DEST/CLAUDE.md"
[ -f "$SRC/RTK.md" ] && { backup "$DEST/RTK.md"; cp "$SRC/RTK.md" "$DEST/RTK.md"; }

# 2. settings.json (substitute __HOME__ -> real $HOME, __ZAI_TOKEN__ -> $ZAI_TOKEN)
backup "$DEST/settings.json"
if [ -z "${ZAI_TOKEN:-}" ] && [ -f "$DEST/settings.json.bak-$TS" ]; then
  # reuse token from the settings we just backed up (re-install on same machine)
  ZAI_TOKEN="$(sed -n 's/.*"ANTHROPIC_AUTH_TOKEN"[^"]*"\([^"]*\)".*/\1/p' "$DEST/settings.json.bak-$TS" | head -1)"
fi
if [ -z "${ZAI_TOKEN:-}" ]; then
  read -r -p "   z.ai ANTHROPIC_AUTH_TOKEN (blank = leave placeholder): " ZAI_TOKEN || true
fi
sed -e "s|__HOME__|$HOME|g" -e "s|__ZAI_TOKEN__|${ZAI_TOKEN:-__ZAI_TOKEN__}|g" \
  "$SRC/settings.template.json" > "$DEST/settings.json"
[ -z "${ZAI_TOKEN:-}" ] && echo "   ⚠ no token — edit ANTHROPIC_AUTH_TOKEN in ~/.claude/settings.json later"
echo "   wrote settings.json (paths -> $HOME)"

# 3. scripts (statusline.sh lives at ~/.claude root; rest in scripts/)
for f in "$SRC"/scripts/*; do
  b="$(basename "$f")"
  if [ "$b" = "statusline.sh" ]; then cp "$f" "$DEST/statusline.sh"; else cp "$f" "$DEST/scripts/$b"; fi
done
chmod +x "$DEST"/scripts/*.sh "$DEST/statusline.sh" 2>/dev/null || true

# 4. commands, templates, curated memory, agents
cp "$SRC"/commands/*.md   "$DEST/commands/"            2>/dev/null || true
cp "$SRC"/templates/*.md  "$DEST/templates/"           2>/dev/null || true
cp "$SRC"/memory/*.md      "$DEST/projects/-/memory/"  2>/dev/null || true
cp "$SRC"/agents/*.md      "$DEST/agents/"             2>/dev/null || true
cp -R "$SRC"/skills/.       "$DEST/skills/"            2>/dev/null || true

echo "==> Files installed."

# 4b. Cursor bridge (one setup, all tools).
# Cursor auto-discovers skills (~/.claude/skills, ~/.codex/skills) and agents (~/.claude/agents),
# so only slash commands need a link: ~/.cursor/commands -> ~/.claude/commands.
mkdir -p "$HOME/.cursor"
if [ -d "$HOME/.cursor/commands" ] && [ ! -L "$HOME/.cursor/commands" ]; then
  mv "$HOME/.cursor/commands" "$HOME/.cursor/commands.bak-$TS"
  echo "   backed up existing ~/.cursor/commands"
fi
ln -sfn "$DEST/commands" "$HOME/.cursor/commands"
echo "   linked ~/.cursor/commands -> ~/.claude/commands (Cursor bridge)"

# 5. external CLIs (best-effort via Homebrew; Bash hook degrades gracefully if absent)
echo "==> Installing CLIs (Homebrew)..."
if command -v brew >/dev/null 2>&1; then
  brew install jq node 2>/dev/null || true
  brew install rtk lowfat 2>/dev/null || echo "   ⚠ rtk/lowfat not in default taps — see MANIFEST.md (hook passthrough-degrades until installed)"
  brew install --cask obsidian 2>/dev/null || true
else
  echo "   ⚠ Homebrew absent — install jq node rtk lowfat yourself (MANIFEST.md)"
fi

# 6. plugins (headless — no manual /plugin needed). ECC/harness/claudeclaw intentionally omitted.
if command -v claude >/dev/null 2>&1; then
  echo "==> Installing plugins (claude plugin CLI)..."
  for m in forrestchang/andrej-karpathy-skills JuliusBrussee/caveman thedotmack/claude-mem; do
    claude plugin marketplace add "$m" 2>/dev/null || true
  done
  for p in superpowers@claude-plugins-official clangd-lsp@claude-plugins-official \
           caveman@caveman claude-mem@thedotmack andrej-karpathy-skills@karpathy-skills; do
    claude plugin install "$p" 2>/dev/null && echo "   ✓ $p" || echo "   ⚠ $p — retry: claude plugin install $p"
  done
else
  echo "   ⚠ 'claude' CLI not on PATH — install plugins via MANIFEST.md"
fi

echo "==> Verify:"; for c in rtk lowfat jq claude; do command -v "$c" >/dev/null 2>&1 && echo "   ✓ $c" || echo "   ✗ $c"; done

cat <<'EOF'

==> DONE — one-command bootstrap complete.
  • Restart `claude` → claude-mem recall + hooks + routing + delegation active.
  • (optional) open Obsidian on ~/.claude/projects/-/memory for the knowledge graph.
  • (optional) bash prune-agents.sh  if a full agent pack ever gets re-added.
EOF
