#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP="${1:-$ROOT/desktop/gpui/target/release/bundle/macos/Codinal.app}"
EXECUTABLE="$APP/Contents/MacOS/codinal"
RUNTIME="$APP/Contents/Resources/codinal-runtime"

test -x "$EXECUTABLE"
if [ "${CODINAL_SKIP_EMBEDDED_IMPORTS:-0}" != "1" ]; then
  test -x "$RUNTIME"
  file "$EXECUTABLE" "$RUNTIME" | grep -q 'arm64'
fi

if [ "${CODINAL_SKIP_CODESIGN_CHECK:-0}" != "1" ]; then
  codesign --verify --deep --strict --verbose=2 "$APP"
fi

if [ "${CODINAL_SKIP_APP_LAUNCH:-0}" != "1" ]; then
  SMOKE_HOME="$(mktemp -d /tmp/codinal-smoke-home.XXXXXX)"
  BASELINE_RUNTIME_PIDS=" $(pgrep -f '/Contents/Resources/codinal-runtime$' | tr '\n' ' ' || true)"
  HOME="$SMOKE_HOME" "$EXECUTABLE" &
  APP_PID=$!
  REAL_APP_PID=""
  RUNTIME_PID=""
  cleanup() {
    for candidate in "$RUNTIME_PID" "$REAL_APP_PID" "$APP_PID"; do
      if [ -n "$candidate" ]; then
        kill "$candidate" >/dev/null 2>&1 || true
      fi
    done
    for _ in $(seq 1 10); do
      RUNNING=0
      for candidate in "$RUNTIME_PID" "$REAL_APP_PID" "$APP_PID"; do
        if [ -n "$candidate" ] && kill -0 "$candidate" >/dev/null 2>&1; then
          RUNNING=1
        fi
      done
      if [ "$RUNNING" = "0" ]; then
        break
      fi
      sleep 1
    done
    for candidate in "$RUNTIME_PID" "$REAL_APP_PID" "$APP_PID"; do
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
      RUNTIME_PID="$candidate"
      REAL_APP_PID="$(ps -o ppid= -p "$candidate" | tr -d ' ')"
      break
    done < <(pgrep -f '/Contents/Resources/codinal-runtime$' || true)
    if [ -n "$RUNTIME_PID" ]; then
      break
    fi
    sleep 1
  done

  if [ -z "$RUNTIME_PID" ]; then
    echo "packaged native runtime did not start" >&2
    exit 1
  fi

  FORBIDDEN_CHILDREN="$(ps -axo pid=,ppid=,command= | awk -v parent="$APP_PID" '$2 == parent && $0 ~ /([Pp]ython|[Tt]auri|[Ww]eb[Kk]it|[Ww]eb[Vv]iew)/')"
  if [ -n "$FORBIDDEN_CHILDREN" ]; then
    echo "packaged Codinal spawned a forbidden non-Rust child:" >&2
    echo "$FORBIDDEN_CHILDREN" >&2
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
