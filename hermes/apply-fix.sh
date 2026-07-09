#!/usr/bin/env bash
# Apply the Hermes anti-loop fix from a local harness-flow clone (repo is private).
# Usage:
#   bash hermes/apply-fix.sh              # from repo, or auto-find clone
#   hermes-apply-fix                      # after install.sh copies to ~/.local/bin
set -euo pipefail

OLD_USER="/Users/pongsathonkheeereekaew"
HERMES_DIR="${HERMES_DIR:-$HOME/.hermes}"
BACKUP_TS="$(date +%Y%m%d-%H%M%S)"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

find_repo() {
  local d
  for d in \
    "${HARNESS_FLOW_DIR:-}" \
    "$SCRIPT_DIR/.." \
    "$HOME/harness-flow" \
    "$HOME/easby-workflow" \
    "$HOME/claude-workflow" \
    "$HOME/Downloads/harness-flow" \
    "$HOME/Downloads/easby-workflow"; do
    [ -n "$d" ] && [ -f "$d/hermes/config.yaml" ] && [ -f "$d/hermes/SOUL.md" ] && {
      echo "$(cd "$d" && pwd)"
      return 0
    }
  done
  return 1
}

REPO_DIR="$(find_repo)" || {
  echo "ERROR: harness-flow repo not found."
  echo "  Clone: git clone git@github.com:pongsathonkheereekaew/harness-flow.git ~/harness-flow"
  echo "  Or set: HARNESS_FLOW_DIR=/path/to/harness-flow"
  exit 1
}

echo "==> Hermes anti-loop fix"
echo "   repo: $REPO_DIR"

if [ -d "$REPO_DIR/.git" ]; then
  git -C "$REPO_DIR" pull --ff-only origin main 2>/dev/null \
    && echo "   git pull: ok" \
    || echo "   git pull: skipped (offline or dirty)"
fi

mkdir -p "$HERMES_DIR"
for f in config.yaml SOUL.md; do
  if [ -f "$HERMES_DIR/$f" ]; then
    cp "$HERMES_DIR/$f" "$HERMES_DIR/$f.bak-$BACKUP_TS"
    echo "   backed up $f"
  fi
done

sed "s#${OLD_USER}#${HOME}#g" "$REPO_DIR/hermes/config.yaml" > "$HERMES_DIR/config.yaml"
cp "$REPO_DIR/hermes/SOUL.md" "$HERMES_DIR/SOUL.md"
echo "   wrote config.yaml + SOUL.md -> $HERMES_DIR"

UID_="$(id -u)"
PLIST="$HOME/Library/LaunchAgents/com.nousresearch.hermes.plist"
if [ -f "$PLIST" ]; then
  launchctl kickstart -k "gui/${UID_}/com.nousresearch.hermes" 2>/dev/null \
    && echo "   restarted gateway (launchd kickstart)" \
    || { launchctl bootout "gui/${UID_}/com.nousresearch.hermes" 2>/dev/null || true
         launchctl bootstrap "gui/${UID_}" "$PLIST"
         echo "   restarted gateway (launchd bootstrap)"; }
elif command -v hermes >/dev/null 2>&1; then
  hermes gateway restart 2>/dev/null || true
  echo "   restarted gateway (hermes CLI)"
else
  echo "   ⚠ no launchd plist or hermes CLI — copy done; restart gateway manually"
fi

echo "==> Done. Test: one Telegram message -> one reply bubble."
