#!/usr/bin/env bash
# Apply the Hermes anti-loop fix from harness-flow (no git clone required).
# Usage:  bash hermes/apply-fix.sh
#    or:  curl -fsSL https://raw.githubusercontent.com/pongsathonkheereekaew/harness-flow/main/hermes/apply-fix.sh | bash
set -euo pipefail

REPO="${HARNESS_FLOW_REPO:-pongsathonkheereekaew/harness-flow}"
BRANCH="${HARNESS_FLOW_BRANCH:-main}"
BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}/hermes"
OLD_USER="/Users/pongsathonkheeereekaew"
HERMES_DIR="${HERMES_DIR:-$HOME/.hermes}"
BACKUP_TS="$(date +%Y%m%d-%H%M%S)"

echo "==> Hermes anti-loop fix (branch: ${BRANCH})"

mkdir -p "$HERMES_DIR"
for f in config.yaml SOUL.md; do
  if [ -f "$HERMES_DIR/$f" ]; then
    cp "$HERMES_DIR/$f" "$HERMES_DIR/$f.bak-$BACKUP_TS"
    echo "   backed up $f"
  fi
done

tmp="$(mktemp)"
curl -fsSL "$BASE/config.yaml" -o "$tmp"
sed "s#${OLD_USER}#${HOME}#g" "$tmp" > "$HERMES_DIR/config.yaml"
rm -f "$tmp"
curl -fsSL "$BASE/SOUL.md" -o "$HERMES_DIR/SOUL.md"
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
  hermes gateway restart 2>/dev/null || hermes gateway run --replace &
  echo "   restarted gateway (hermes CLI)"
else
  echo "   ⚠ no launchd plist or hermes CLI — copy done; restart gateway manually"
fi

echo "==> Done. Send one test message in Telegram — expect one reply bubble per turn."
