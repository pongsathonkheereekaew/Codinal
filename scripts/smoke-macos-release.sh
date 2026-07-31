#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${1:-$ROOT/desktop/src-tauri/target/release/bundle/macos/Codinal.app}"
EXECUTABLE="$APP/Contents/MacOS/codinal"
PYTHON="$APP/Contents/Resources/python/bin/python3"

test -x "$EXECUTABLE"
test -x "$PYTHON"
if [ "${CODINAL_SKIP_CODESIGN_CHECK:-0}" != "1" ]; then
  codesign --verify --deep --strict --verbose=2 "$APP"
fi
if [ "${CODINAL_SKIP_EMBEDDED_IMPORTS:-0}" != "1" ]; then
  "$PYTHON" -B -c \
    'import anthropic, fastapi, google.genai, mcp, openai'
  if [ ! -f "$APP/Contents/Resources/runtime/runtime/control_plane/app.py" ]; then
    echo "packaged control-plane application missing" >&2
    exit 1
  fi
  grep -q "/v1/sessions/.*/mcp/connect" \
    "$APP/Contents/Resources/runtime/runtime/control_plane/app.py" \
    || { echo "packaged MCP connect route missing" >&2; exit 1; }
  grep -q "/v1/sessions/.*/mcp/servers" \
    "$APP/Contents/Resources/runtime/runtime/control_plane/app.py" \
    || { echo "packaged MCP list/disconnect routes missing" >&2; exit 1; }
fi

if [ "${CODINAL_SKIP_APP_LAUNCH:-0}" != "1" ]; then
  "$EXECUTABLE" &
  APP_PID=$!
  cleanup() {
    kill "$APP_PID" >/dev/null 2>&1 || true
    for _ in $(seq 1 10); do
      if ! kill -0 "$APP_PID" >/dev/null 2>&1; then
        wait "$APP_PID" >/dev/null 2>&1 || true
        return
      fi
      sleep 1
    done
    kill -KILL "$APP_PID" >/dev/null 2>&1 || true
    wait "$APP_PID" >/dev/null 2>&1 || true
  }
  trap cleanup EXIT

  SIDECAR_PID=""
  for _ in $(seq 1 20); do
    while IFS= read -r candidate; do
      if ps -o command= -p "$candidate" | grep -q -- \
        "-B -m runtime.control_plane"; then
        SIDECAR_PID="$candidate"
        break
      fi
    done < <(pgrep -P "$APP_PID" || true)
    if [ -n "$SIDECAR_PID" ]; then
      break
    fi
    sleep 1
  done

  if [ -z "$SIDECAR_PID" ]; then
    echo "packaged control-plane sidecar did not start" >&2
    exit 1
  fi

  cleanup
  trap - EXIT
else
  echo "Codinal packaged smoke launched skipped by configuration"
fi

if [ "${CODINAL_SKIP_CODESIGN_CHECK:-0}" != "1" ]; then
  codesign --verify --deep --strict --verbose=2 "$APP"
else
  echo "skipping codesign verification by configuration"
fi
echo "packaged app smoke test passed"
