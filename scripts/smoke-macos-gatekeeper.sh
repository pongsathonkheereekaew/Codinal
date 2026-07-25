#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(
  python3 -c \
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
xcrun stapler validate "$APP"
spctl --assess --type execute --verbose=2 "$APP"
bash "$ROOT/scripts/smoke-macos-release.sh" "$APP"

echo "quarantined release smoke test passed"
