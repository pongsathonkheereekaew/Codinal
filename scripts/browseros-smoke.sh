#!/usr/bin/env bash
# BrowserOS-native smoke: finds an installed BrowserOS/BrowserOS neo app,
# starts it, and probes its MCP streamable HTTP endpoint. Skips cleanly when
# the binary is not installed.
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

MCP_URL="http://127.0.0.1:9010/mcp"
if ! curl -sS --max-time 2 "$MCP_URL" -o /dev/null 2>/dev/null; then
  open -a "$(basename "$(dirname "$(dirname "$BIN")")")"
  for _ in $(seq 1 30); do
    if curl -sS --max-time 2 "$MCP_URL" -o /dev/null 2>/dev/null; then
      break
    fi
    sleep 1
  done
fi

INIT=$(curl -sS --max-time 5 -X POST "$MCP_URL" \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"cedia-smoke","version":"0.1.0"}}}' \
  || true)
if ! printf '%s' "$INIT" | grep -q 'browseros-neo'; then
  echo "browseros smoke: FAIL (MCP endpoint did not answer on $MCP_URL)"
  exit 1
fi
echo "browseros smoke: PASS ($BIN -> $MCP_URL)"
