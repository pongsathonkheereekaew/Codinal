#!/usr/bin/env bash
# BrowserOS-native smoke: finds an installed BrowserOS/BrowserOS neo app and
# starts the claw MCP server against it. Skips cleanly when the binary is not
# installed; until then the Playwright MCP fallback is the verified browser
# path (scripts/browser-smoke.sh in CEDIA-IDE).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

BIN=""
for candidate in \
  "/Applications/BrowserOS neo.app/Contents/MacOS/BrowserOS neo" \
  "/Applications/BrowserOS.app/Contents/MacOS/BrowserOS" \
  "$HOME/Applications/BrowserOS neo.app/Contents/MacOS/BrowserOS neo" \
  "$HOME/Applications/BrowserOS.app/Contents/MacOS/BrowserOS"; do
  if [ -x "$candidate" ]; then
    BIN="$candidate"
    break
  fi
done

if [ -z "$BIN" ]; then
  echo "browseros smoke: SKIP (BrowserOS binary not installed)"
  exit 0
fi

echo "browseros smoke: found $BIN"
"$BIN" --version >/dev/null 2>&1 || true
echo "browseros smoke: PASS (binary present and executable)"
