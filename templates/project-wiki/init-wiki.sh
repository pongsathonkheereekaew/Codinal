#!/usr/bin/env bash
# Copy the project-wiki scaffold into a target git repo root.
# Usage: bash templates/project-wiki/init-wiki.sh /path/to/repo
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST="${1:-}"

if [ -z "$DEST" ]; then
  echo "Usage: $0 /path/to/target-repo" >&2
  exit 1
fi

if [ ! -d "$DEST" ]; then
  echo "ERROR: destination does not exist: $DEST" >&2
  exit 1
fi

DEST="$(cd "$DEST" && pwd)"

if [ -f "$DEST/docs/wiki/SCHEMA.md" ]; then
  echo "Wiki already present at $DEST/docs/wiki — refusing to overwrite." >&2
  exit 1
fi

mkdir -p "$DEST/docs/wiki"/{raw,incidents,code-map,patterns} "$DEST/.cursor/rules"

cp "$SRC/SCHEMA.md" "$DEST/docs/wiki/SCHEMA.md"
cp "$SRC/docs/wiki/index.md" "$DEST/docs/wiki/index.md"
cp "$SRC/docs/wiki/log.md" "$DEST/docs/wiki/log.md"
cp "$SRC/docs/wiki/raw/.gitkeep" "$DEST/docs/wiki/raw/.gitkeep"
cp "$SRC/docs/wiki/incidents/.gitkeep" "$DEST/docs/wiki/incidents/.gitkeep"
cp "$SRC/docs/wiki/code-map/.gitkeep" "$DEST/docs/wiki/code-map/.gitkeep"
cp "$SRC/docs/wiki/patterns/.gitkeep" "$DEST/docs/wiki/patterns/.gitkeep"
cp "$SRC/.cursor/rules/project-wiki.mdc" "$DEST/.cursor/rules/project-wiki.mdc"

# Stamp init date in log
TODAY="$(date +%Y-%m-%d)"
if grep -q '| | wiki initialized |' "$DEST/docs/wiki/log.md" 2>/dev/null; then
  sed -i.bak "s/| | wiki initialized |/| $TODAY | wiki initialized |/" "$DEST/docs/wiki/log.md"
  rm -f "$DEST/docs/wiki/log.md.bak"
fi

echo "Initialized project wiki at $DEST/docs/wiki"
echo "Cursor rule: $DEST/.cursor/rules/project-wiki.mdc"
echo "Commit when ready. Agents will write incidents after validated fixes."
