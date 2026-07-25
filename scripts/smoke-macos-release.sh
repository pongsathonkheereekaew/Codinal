#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${1:-$ROOT/desktop/src-tauri/target/release/bundle/macos/Codinal.app}"
EXECUTABLE="$APP/Contents/MacOS/codinal"
PYTHON="$APP/Contents/Resources/python/bin/python3"

test -x "$EXECUTABLE"
test -x "$PYTHON"
codesign --verify --deep --strict --verbose=2 "$APP"
"$PYTHON" -B -c \
  'import anthropic, fastapi, google.genai, mcp, openai'

"$EXECUTABLE" &
APP_PID=$!
cleanup() {
  kill "$APP_PID" >/dev/null 2>&1 || true
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
codesign --verify --deep --strict --verbose=2 "$APP"
echo "packaged app smoke test passed"
