#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${1:-$ROOT/desktop/gpui/target/release/bundle/macos/Codinal.app}"
EXECUTABLE="$APP/Contents/MacOS/codinal"
RUNTIME="$APP/Contents/Resources/codinal-runtime"

test -x "$EXECUTABLE"
test -x "$RUNTIME"
if [ "${CODINAL_SKIP_CODESIGN_CHECK:-0}" != "1" ]; then
  codesign --verify --deep --strict --verbose=2 "$APP"
fi
file "$EXECUTABLE" "$RUNTIME" | grep -q 'arm64'

if [ "${CODINAL_SKIP_APP_LAUNCH:-0}" != "1" ]; then
  SMOKE_HOME="$(mktemp -d /tmp/codinal-smoke-home.XXXXXX)"
  BASELINE_RUNTIME_PIDS=" $(pgrep -f '/Contents/Resources/codinal-runtime$' | tr '\n' ' ' || true)"
  HOME="$SMOKE_HOME" "$EXECUTABLE" &
  APP_PID=$!
  REAL_APP_PID=""
  SIDECAR_PID=""
  cleanup() {
    for candidate in "$SIDECAR_PID" "$REAL_APP_PID" "$APP_PID"; do
      if [ -n "$candidate" ]; then
        kill "$candidate" >/dev/null 2>&1 || true
      fi
    done
    for _ in $(seq 1 10); do
      RUNNING=0
      for candidate in "$SIDECAR_PID" "$REAL_APP_PID" "$APP_PID"; do
        if [ -n "$candidate" ] && kill -0 "$candidate" >/dev/null 2>&1; then
          RUNNING=1
        fi
      done
      if [ "$RUNNING" = "0" ]; then
        break
      fi
      sleep 1
    done
    for candidate in "$SIDECAR_PID" "$REAL_APP_PID" "$APP_PID"; do
      if [ -n "$candidate" ]; then
        kill -KILL "$candidate" >/dev/null 2>&1 || true
      fi
    done
    wait "$APP_PID" >/dev/null 2>&1 || true
    rm -rf "$SMOKE_HOME"
  }
  trap cleanup EXIT

  for _ in $(seq 1 20); do
    while IFS= read -r candidate; do
      case "$BASELINE_RUNTIME_PIDS" in
        *" $candidate "*) continue ;;
      esac
      SIDECAR_PID="$candidate"
      REAL_APP_PID="$(ps -o ppid= -p "$candidate" | tr -d ' ')"
      break
    done < <(pgrep -f '/Contents/Resources/codinal-runtime$' || true)
    if [ -n "$SIDECAR_PID" ]; then
      break
    fi
    sleep 1
  done

  if [ -z "$SIDECAR_PID" ]; then
    echo "packaged native runtime did not start" >&2
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
