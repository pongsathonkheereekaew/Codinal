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

# 2. settings.json (substitute __HOME__ -> real $HOME)
backup "$DEST/settings.json"
sed "s|__HOME__|$HOME|g" "$SRC/settings.template.json" > "$DEST/settings.json"
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

# 5. dependency checks (warn, don't fail)
echo "==> Checking external deps:"
for c in rtk lowfat jq git; do
  if command -v "$c" >/dev/null 2>&1; then echo "   ✓ $c"; else echo "   ✗ $c  MISSING — see MANIFEST.md"; fi
done
if ! command -v rtk >/dev/null 2>&1 || ! command -v lowfat >/dev/null 2>&1; then
  echo "   ⚠ rtk/lowfat missing → the PreToolUse Bash hook will error."
  echo "     Install them (MANIFEST.md) OR remove the PreToolUse block from $DEST/settings.json until you do."
fi

cat <<'EOF'

==> NEXT (manual, one-time):
  1. Install CLIs + apps  → see MANIFEST.md  (rtk, lowfat, jq, Obsidian, node)
  2. Install plugins      → launch `claude`, then run the /plugin commands in MANIFEST.md
  3. (optional) trim the agent pack → bash prune-agents.sh
  4. Restart `claude`. claude-mem auto-recall + hooks + routing now active.
  5. (optional) open Obsidian on ~/.claude/projects/-/memory for the knowledge graph.
Done.
EOF
