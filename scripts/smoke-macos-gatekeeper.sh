#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PYTHON_BIN="${CODINAL_PYTHON_BIN:-python3}"
if ! "$PYTHON_BIN" -c 'import tomllib' >/dev/null 2>&1; then
  if command -v /opt/homebrew/bin/python3 >/dev/null; then
    PYTHON_BIN="/opt/homebrew/bin/python3"
  fi
fi
if ! "$PYTHON_BIN" -c 'import tomllib' >/dev/null 2>&1; then
  echo "tomllib is required for version read; set CODINAL_PYTHON_BIN to Python 3.11+" >&2
  exit 1
fi

VERSION="$(
  "$PYTHON_BIN" -c \
    'import sys, tomllib; print(tomllib.load(open(sys.argv[1], "rb"))["package"]["version"])' \
    "$ROOT/desktop/src-tauri/Cargo.toml"
)"
ZIP="${1:-$ROOT/desktop/src-tauri/target/release/bundle/Codinal-${VERSION}-macos-arm64.zip}"
SMOKE_ROOT="$(mktemp -d /tmp/codinal-gatekeeper.XXXXXX)"
trap 'rm -rf "$SMOKE_ROOT"' EXIT

test -f "$ZIP"
ditto -x -k "$ZIP" "$SMOKE_ROOT"
APP="$SMOKE_ROOT/Codinal.app"
test -d "$APP"
xattr -w com.apple.quarantine "0081;00000000;Codinal;" "$APP"
if [ "${CODINAL_REQUIRE_NOTARIZATION:-1}" = "1" ]; then
  xcrun stapler validate "$APP"
  spctl --assess --type execute --verbose=2 "$APP"
else
  echo "Codinal gatekeeper smoke running without stapled/notarization validation"
fi

CODINAL_SKIP_APP_LAUNCH=1 \
CODINAL_SKIP_EMBEDDED_IMPORTS=1 \
bash "$ROOT/scripts/smoke-macos-release.sh" "$APP"

echo "quarantined release smoke test passed"
