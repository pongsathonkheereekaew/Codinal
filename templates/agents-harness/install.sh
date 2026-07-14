#!/usr/bin/env bash
# Bootstrap Agent Harness into ~/.agents (idempotent; won't overwrite AGENTS.md).
set -euo pipefail

SRC="$(cd "$(dirname "$0")" && pwd)"
DEST="${AGENTS_HOME:-$HOME/.agents}"

echo "=== Agent Harness install → $DEST ==="
mkdir -p "$DEST"/{skills,standards,commands,scripts}

# Policy: only create if missing
if [[ ! -f "$DEST/AGENTS.md" ]]; then
  cp "$SRC/AGENTS.md" "$DEST/AGENTS.md"
  echo "created AGENTS.md"
else
  echo "keep existing AGENTS.md (not overwritten)"
fi

# Scripts: always refresh from template (they're the CLI)
cp -f "$SRC"/scripts/* "$DEST/scripts/"
chmod +x "$DEST/scripts/"*

# Standards: seed examples if missing
if [[ ! -f "$DEST/standards/writing.md" ]]; then
  cp -f "$SRC/standards/"*.md "$DEST/standards/" 2>/dev/null || true
  cp -f "$SRC/standards/cursor.meta.yaml" "$DEST/standards/" 2>/dev/null || true
  echo "seeded standards/"
else
  echo "keep existing standards/ (seed skipped)"
fi

# --- adapters (best-effort, non-destructive) ---

# Claude: ensure @AGENTS.md at top if CLAUDE.md exists and lacks it
CLAUDE_MD="$HOME/.claude/CLAUDE.md"
if [[ -f "$CLAUDE_MD" ]]; then
  if ! grep -q 'AGENTS.md' "$CLAUDE_MD"; then
    tmp="$(mktemp)"
    {
      echo "# Shared policy (all tools) — load first"
      echo "@../.agents/AGENTS.md"
      echo ""
      cat "$CLAUDE_MD"
    } >"$tmp"
    mv "$tmp" "$CLAUDE_MD"
    echo "prepended @AGENTS.md to ~/.claude/CLAUDE.md"
  else
    echo "Claude already references AGENTS.md"
  fi
elif [[ -d "$HOME/.claude" ]]; then
  cp "$SRC/adapters/CLAUDE.md.example" "$CLAUDE_MD"
  echo "created ~/.claude/CLAUDE.md from example"
fi

# Policy symlinks for tools that read AGENTS.md / GEMINI.md
link_policy() {
  local dest="$1" rel="$2"
  mkdir -p "$(dirname "$dest")"
  if [[ -L "$dest" ]]; then
    echo "OK symlink $dest"
  elif [[ -e "$dest" ]]; then
    echo "WARN $dest exists as real file — leave untouched"
  else
    ln -s "$rel" "$dest"
    echo "linked $dest -> $rel"
  fi
}

link_policy "$HOME/.codex/AGENTS.md" "../.agents/AGENTS.md"
link_policy "$HOME/.zcode/AGENTS.md" "../.agents/AGENTS.md"
mkdir -p "$HOME/.config/opencode"
link_policy "$HOME/.config/opencode/AGENTS.md" "../../.agents/AGENTS.md"
mkdir -p "$HOME/.gemini"
link_policy "$HOME/.gemini/GEMINI.md" "../.agents/AGENTS.md"

echo ""
echo "=== Hermes (manual one-liner) ==="
echo "Add to ~/.hermes/config.yaml:"
echo ""
cat "$SRC/adapters/hermes-skills.snippet.yaml"
echo ""
echo "Keep ~/.hermes/SOUL.md thin — see adapters/SOUL.md.example"
echo ""
echo "Next:"
echo "  $DEST/scripts/harness sync"
echo "  $DEST/scripts/harness doctor"
echo "=== done ==="
