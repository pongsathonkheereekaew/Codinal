#!/usr/bin/env bash
# Install claude/ workflow into ~/.claude (skills, agents, hooks, commands).
# Called by harness-flow/install.sh — idempotent.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$REPO/claude"
DEST="$HOME/.claude"
TS="$(date +%Y%m%d-%H%M%S)"

[ -d "$SRC/skills" ] || { echo "ERROR: $SRC/skills missing — run: git checkout 6aeca1e^ -- claude/"; exit 1; }

echo "==> Installing Claude Code workflow into $DEST"
mkdir -p "$DEST"/{scripts,commands,templates,agents,skills} "$DEST/projects/-/memory"

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
cp -R "$SRC"/skills/.       "$DEST/skills/"

# Fix easby top-level shortcuts (repo symlinks point to wrong Mastering/Producer/Mixing paths)
for pair in "easby-mastering:easby/easby-mastering" "easby-mixing:easby/easby-mixing" "easby-producer:easby/easby-producer"; do
  name="${pair%%:*}"; target="${pair##*:}"
  ln -sfn "$target" "$DEST/skills/$name"
done

# External skill packs → ~/.agents/skills (repo symlinks expect them there)
mkdir -p "$HOME/.agents/skills"
if command -v skills >/dev/null 2>&1; then
  skills add mattpocock/skills -g -y --all -a claude-code 2>/dev/null || true
  skills add google/skills      -g -y --all -a claude-code 2>/dev/null || true
  skills add JuliusBrussee/caveman -g -y -s caveman -a claude-code 2>/dev/null || true
fi
# Matt Pocock renamed skills — keep old symlink names working
AGENTS="$HOME/.agents/skills"
for pair in "to-prd:to-spec" "to-issues:to-tickets" "zoom-out:wayfinder" "diagnose:diagnosing-bugs" "write-a-skill:writing-great-skills"; do
  old="${pair%%:*}"; new="${pair##*:}"
  [ ! -e "$AGENTS/$old" ] && [ -d "$AGENTS/$new" ] && ln -sfn "$new" "$AGENTS/$old"
done

# Merge newer nuiny from Cursor if present
if [ -d "$HOME/.cursor/skills/nuiny" ]; then
  rm -rf "$DEST/skills/insurance/nuiny"
  cp -R "$HOME/.cursor/skills/nuiny" "$DEST/skills/insurance/nuiny"
  ln -sfn "insurance/nuiny" "$DEST/skills/nuiny"
fi

mkdir -p "$HOME/.cursor"
ln -sfn "$DEST/commands" "$HOME/.cursor/commands"

[ -x "$DEST/skills/easby/setup.sh" ] && bash "$DEST/skills/easby/setup.sh" || true

echo "   skills: $(find "$DEST/skills" -maxdepth 1 -mindepth 1 | wc -l | tr -d ' ') | agents: $(ls "$DEST/agents" | wc -l | tr -d ' ')"
