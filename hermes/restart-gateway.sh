#!/usr/bin/env bash
# Restart Hermes Telegram gateway (launchd). Run on Mac when bot stops responding.
set -euo pipefail
UID_="$(id -u)"
PLIST="$HOME/Library/LaunchAgents/com.nousresearch.hermes.plist"
mkdir -p "$HOME/.hermes/logs"

if [ ! -f "$PLIST" ]; then
  echo "ERROR: $PLIST missing — run: cd harness-flow/hermes && ./install.sh"
  exit 1
fi

launchctl bootout "gui/${UID_}/com.nousresearch.hermes" 2>/dev/null || true
sleep 1
launchctl bootstrap "gui/${UID_}" "$PLIST"
sleep 2
launchctl kickstart -k "gui/${UID_}/com.nousresearch.hermes" 2>/dev/null || true

echo "Gateway restarted. Wait ~10s, then send a test message in Telegram."
pgrep -fl "hermes gateway" || echo "(no process yet — check: bash hermes/doctor.sh)"
