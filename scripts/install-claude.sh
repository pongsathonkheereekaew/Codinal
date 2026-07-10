#!/usr/bin/env bash
# Install claude/ workflow into ~/.claude (skills, agents, hooks, commands).
# Called by harness-flow/install.sh — idempotent.
#
# Source of truth: this repo (harness-flow/claude/).
# External packs (mattpocock, google, caveman) install into ~/.agents/skills/
# and are symlinked into ~/.claude/skills/ at install time — not committed here.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/claude"
DEST="$HOME/.claude"
AGENTS="$HOME/.agents/skills"
TS="$(date +%Y%m%d-%H%M%S)"

[ -d "$SRC/skills" ] || { echo "ERROR: $SRC/skills missing"; exit 1; }

echo "==> Installing Claude Code workflow into $DEST"
mkdir -p "$DEST"/{scripts,commands,templates,agents,skills} "$DEST/projects/-/memory" "$AGENTS"

backup() { [ -e "$1" ] && cp -a "$1" "$1.bak-$TS" && echo "   backed up $(basename "$1")" || true; }

backup "$DEST/CLAUDE.md"; cp "$SRC/CLAUDE.md" "$DEST/CLAUDE.md"
[ -f "$SRC/RTK.md" ] && { backup "$DEST/RTK.md"; cp "$SRC/RTK.md" "$DEST/RTK.md"; }

ZAI_TOKEN="${ZAI_TOKEN:-}"
if [ -z "$ZAI_TOKEN" ] && [ -f "$DEST/settings.json" ]; then
  ZAI_TOKEN="$(python3 -c "import json;print(json.load(open('$DEST/settings.json')).get('env',{}).get('ANTHROPIC_AUTH_TOKEN',''))" 2>/dev/null || true)"
fi
sed -e "s|__HOME__|$HOME|g" -e "s|__ZAI_TOKEN__|${ZAI_TOKEN:-__ZAI_TOKEN__}|g" \
  "$SRC/settings.template.json" > "$DEST/settings.json"

for f in "$SRC"/scripts/*; do
  b="$(basename "$f")"
  if [ "$b" = "statusline.sh" ]; then cp "$f" "$DEST/statusline.sh"; else cp "$f" "$DEST/scripts/$b"; fi
done
chmod +x "$DEST"/scripts/*.sh "$DEST/statusline.sh" 2>/dev/null || true

cp "$SRC"/commands/*.md   "$DEST/commands/" 2>/dev/null || true
cp "$SRC"/templates/*.md  "$DEST/templates/" 2>/dev/null || true
cp "$SRC"/memory/*.md      "$DEST/projects/-/memory/" 2>/dev/null || true
cp "$SRC"/agents/*.md      "$DEST/agents/" 2>/dev/null || true

# Personal / bundled skills only (real dirs + in-repo aliases)
rsync -a --delete \
  --exclude '.DS_Store' \
  "$SRC/skills/" "$DEST/skills/" 2>/dev/null \
  || { rm -rf "$DEST/skills"; mkdir -p "$DEST/skills"; cp -R "$SRC/skills/." "$DEST/skills/"; }

# External skill packs → ~/.agents/skills
if command -v skills >/dev/null 2>&1; then
  echo "==> Installing external skill packs (skills CLI)..."
  skills add mattpocock/skills -g -y --all -a claude-code 2>/dev/null || true
  skills add google/skills      -g -y --all -a claude-code 2>/dev/null || true
  skills add JuliusBrussee/caveman -g -y -s caveman -a claude-code 2>/dev/null || true
else
  echo "   ⚠ 'skills' CLI missing — install: npm i -g skills"
  echo "   then: skills add mattpocock/skills -g -y --all -a claude-code"
fi

# Matt Pocock renames — keep old names working
for pair in "to-prd:to-spec" "to-issues:to-tickets" "zoom-out:wayfinder" "diagnose:diagnosing-bugs" "write-a-skill:writing-great-skills"; do
  old="${pair%%:*}"; new="${pair##*:}"
  [ ! -e "$AGENTS/$old" ] && [ -d "$AGENTS/$new" ] && ln -sfn "$new" "$AGENTS/$old"
done

# Symlink every ~/.agents/skills/* into ~/.claude/skills/ (skip if personal skill already present)
for d in "$AGENTS"/*; do
  [ -d "$d" ] || continue
  name="$(basename "$d")"
  dest="$DEST/skills/$name"
  if [ -e "$dest" ] && [ ! -L "$dest" ]; then
    continue  # personal skill wins
  fi
  ln -sfn "$d" "$dest"
done

mkdir -p "$HOME/.cursor"
ln -sfn "$DEST/commands" "$HOME/.cursor/commands"

[ -x "$DEST/skills/easby/setup.sh" ] && bash "$DEST/skills/easby/setup.sh" || true

echo "   skills: $(find "$DEST/skills" -maxdepth 1 -mindepth 1 | wc -l | tr -d ' ') | agents: $(ls "$DEST/agents" | wc -l | tr -d ' ')"
echo "==> Done. Source of truth: $REPO/claude/"
