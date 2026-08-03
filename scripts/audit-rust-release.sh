#!/usr/bin/env bash
set -euo pipefail

APP="${1:?usage: audit-rust-release.sh APP [SBOM]}"
SBOM="${2:-$APP/Contents/Resources/Codinal-rust-sbom.json}"
CONTENTS="$APP/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"

test -d "$APP"
test -x "$MACOS/codinal"
test -x "$RESOURCES/codinal-runtime"
test -f "$SBOM"

if find "$APP" -print | LC_ALL=C grep -Eiq '/(python([0-9.]*)|tauri|webkit|webview)(/|$)'; then
  echo "forbidden Python/Tauri/WebKit/WebView artifact in release bundle" >&2
  exit 1
fi

if ! grep -Eiq '"name"[[:space:]]*:[[:space:]]*"Codinal Rust runtime"' "$SBOM"; then
  echo "SBOM is not a Codinal Rust runtime inventory" >&2
  exit 1
fi
if grep -Eiq 'python|tauri|webkit|webview' "$SBOM"; then
  echo "forbidden runtime component in Rust SBOM" >&2
  exit 1
fi

if command -v otool >/dev/null 2>&1; then
  for binary in "$MACOS/codinal" "$RESOURCES/codinal-runtime"; do
    if otool -L "$binary" | tail -n +2 | LC_ALL=C grep -Eiq 'python|tauri|webkit|webview|/target/|/usr/local/|/opt/homebrew/'; then
      echo "forbidden or local dynamic dependency in $binary" >&2
      exit 1
    fi
  done
fi

if [ "${CODINAL_SKIP_CODESIGN_CHECK:-0}" != "1" ] && command -v codesign >/dev/null 2>&1; then
  codesign --verify --deep --strict --verbose=2 "$APP"
fi

if [ "${CODINAL_REQUIRE_NOTARIZATION:-0}" = "1" ]; then
  command -v xcrun >/dev/null 2>&1
  xcrun stapler validate "$APP"
  spctl --assess --type execute --verbose=2 "$APP"
fi

echo "Rust-only release audit passed: $APP"
