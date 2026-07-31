#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GPUI_ROOT="$ROOT/desktop/gpui-prototype"
RUNTIME_ROOT="$ROOT/crates/codinal-runtime"
BUNDLE_ROOT="$GPUI_ROOT/target/release/bundle"
APP="$BUNDLE_ROOT/macos/Codinal.app"
CONTENTS="$APP/Contents"
MACOS="$CONTENTS/MacOS"
RESOURCES="$CONTENTS/Resources"
SIGNER_MANIFEST="$ROOT/tools/update-signer/Cargo.toml"
SIGNER_BINARY="$ROOT/tools/update-signer/target/release/codinal-update-signer"

# Capture release credentials as non-exported shell variables, then remove the
# exported originals before any dependency build script can execute.
SIGNING_IDENTITY_VALUE="${APPLE_SIGNING_IDENTITY:-}"
NOTARY_PROFILE_VALUE="${CODINAL_NOTARY_PROFILE:-}"
NOTARY_APPLE_ID_VALUE="${APPLE_ID:-}"
NOTARY_PASSWORD_VALUE="${APPLE_PASSWORD:-}"
NOTARY_TEAM_ID_VALUE="${APPLE_TEAM_ID:-}"
UPDATE_KEY_PATH_VALUE="${CODINAL_UPDATE_SIGNING_PRIVATE_KEY_PATH:-}"
UPDATE_PASSWORD_VALUE="${CODINAL_UPDATE_SIGNING_PASSWORD:-}"
unset APPLE_SIGNING_IDENTITY CODINAL_NOTARY_PROFILE APPLE_ID APPLE_PASSWORD APPLE_TEAM_ID
unset CODINAL_UPDATE_SIGNING_PRIVATE_KEY_PATH CODINAL_UPDATE_SIGNING_PASSWORD

if [ "$(uname -s)" != "Darwin" ] || [ "$(uname -m)" != "arm64" ]; then
  echo "Codinal release builds require Apple Silicon macOS" >&2
  exit 1
fi

APP_VERSION="$({
  awk '
    /^\[package\]$/ { package = 1; next }
    package && /^version = / {
      value = $0
      sub(/^version = "/, "", value)
      sub(/"$/, "", value)
      print value
      exit
    }
  ' "$GPUI_ROOT/Cargo.toml"
})"
test -n "$APP_VERSION"

if [ "${CODINAL_SKIP_CARGO_BUILD:-0}" != "1" ]; then
  TOOLCHAINS="${TOOLCHAINS:-com.apple.dt.toolchain.Metal.32023.864}" \
    cargo build --release --locked --manifest-path "$GPUI_ROOT/Cargo.toml"
  cargo build --release --locked --manifest-path "$RUNTIME_ROOT/Cargo.toml"
  cargo build --release --locked --manifest-path "$SIGNER_MANIFEST"
fi
test -x "$GPUI_ROOT/target/release/codinal-gpui-prototype"
test -x "$RUNTIME_ROOT/target/release/codinal-runtime"
test -x "$SIGNER_BINARY"

rm -rf "$APP"
mkdir -p "$MACOS" "$RESOURCES"
install -m 755 "$GPUI_ROOT/target/release/codinal-gpui-prototype" "$MACOS/codinal"
install -m 755 "$RUNTIME_ROOT/target/release/codinal-runtime" "$RESOURCES/codinal-runtime"
install -m 644 "$ROOT/desktop/src-tauri/icons/icon.icns" "$RESOURCES/Codinal.icns"

INFO_PLIST="$CONTENTS/Info.plist"
plutil -create xml1 "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleDisplayName string Codinal" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleExecutable string codinal" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleIconFile string Codinal" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string dev.codinal.desktop" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleInfoDictionaryVersion string 6.0" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleName string Codinal" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundlePackageType string APPL" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleShortVersionString string $APP_VERSION" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleVersion string $APP_VERSION" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :LSMinimumSystemVersion string 12.0" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :NSHighResolutionCapable bool true" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes array" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0 dict" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleURLName string dev.codinal.desktop" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes array" "$INFO_PLIST"
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes:0 string codinal" "$INFO_PLIST"
plutil -lint "$INFO_PLIST"

test -x "$MACOS/codinal"
test -x "$RESOURCES/codinal-runtime"
if otool -L "$MACOS/codinal" "$RESOURCES/codinal-runtime" \
  | grep -E '^[[:space:]]+(/target/|/usr/local/|/opt/homebrew/)'; then
  echo "release binaries contain non-system local dynamic-library paths" >&2
  exit 1
fi

SIGNING_IDENTITY="$SIGNING_IDENTITY_VALUE"
if [ "${CODINAL_REQUIRE_SIGNING:-0}" = "1" ] && [ -z "$SIGNING_IDENTITY" ]; then
  echo "APPLE_SIGNING_IDENTITY is required for a release build" >&2
  exit 1
fi
if [ -n "$SIGNING_IDENTITY" ]; then
  codesign --force --options runtime --timestamp --sign "$SIGNING_IDENTITY" \
    "$RESOURCES/codinal-runtime"
  codesign --force --options runtime --timestamp --sign "$SIGNING_IDENTITY" \
    "$MACOS/codinal"
  codesign --force --options runtime --timestamp --sign "$SIGNING_IDENTITY" "$APP"
else
  codesign --force --sign - "$RESOURCES/codinal-runtime"
  codesign --force --sign - "$MACOS/codinal"
  codesign --force --sign - "$APP"
fi
codesign --verify --deep --strict --verbose=2 "$APP"

if [ "${CODINAL_REQUIRE_NOTARIZATION:-0}" = "1" ]; then
  NOTARY_ARCHIVE="$(mktemp /tmp/Codinal-notary.XXXXXX.zip)"
  trap 'rm -f "$NOTARY_ARCHIVE"' EXIT
  ditto -c -k --keepParent "$APP" "$NOTARY_ARCHIVE"
  if [ -n "$NOTARY_PROFILE_VALUE" ]; then
    xcrun notarytool submit "$NOTARY_ARCHIVE" \
      --keychain-profile "$NOTARY_PROFILE_VALUE" --wait
  elif [ -n "$NOTARY_APPLE_ID_VALUE" ] && [ -n "$NOTARY_PASSWORD_VALUE" ] && [ -n "$NOTARY_TEAM_ID_VALUE" ]; then
    xcrun notarytool submit "$NOTARY_ARCHIVE" \
      --apple-id "$NOTARY_APPLE_ID_VALUE" --password "$NOTARY_PASSWORD_VALUE" \
      --team-id "$NOTARY_TEAM_ID_VALUE" --wait
  else
    echo "notarization credentials are required" >&2
    exit 1
  fi
  xcrun stapler staple "$APP"
  xcrun stapler validate "$APP"
  spctl --assess --type execute --verbose=2 "$APP"
fi

ARTIFACT="$BUNDLE_ROOT/Codinal-${APP_VERSION}-macos-arm64.zip"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ARTIFACT"
shasum -a 256 "$ARTIFACT" > "$ARTIFACT.sha256"

UPDATER_ARTIFACT="$BUNDLE_ROOT/Codinal-${APP_VERSION}-macos-arm64.app.tar.gz"
COPYFILE_DISABLE=1 tar -czf "$UPDATER_ARTIFACT" -C "$BUNDLE_ROOT/macos" Codinal.app
shasum -a 256 "$UPDATER_ARTIFACT" > "$UPDATER_ARTIFACT.sha256"

UPDATE_KEY_PATH="$UPDATE_KEY_PATH_VALUE"
if [ "${CODINAL_REQUIRE_UPDATE_SIGNING:-0}" = "1" ] && [ -z "$UPDATE_KEY_PATH" ]; then
  echo "CODINAL_UPDATE_SIGNING_PRIVATE_KEY_PATH is required" >&2
  exit 1
fi
if [ -n "$UPDATE_KEY_PATH" ]; then
  test -f "$UPDATE_KEY_PATH"
  CODINAL_UPDATE_SIGNING_PASSWORD="$UPDATE_PASSWORD_VALUE" \
    "$SIGNER_BINARY" "$UPDATE_KEY_PATH" "$UPDATER_ARTIFACT" \
    > "$UPDATER_ARTIFACT.sig"
  test -s "$UPDATER_ARTIFACT.sig"
fi

echo "release app: $APP"
echo "release artifact: $ARTIFACT"
echo "updater artifact: $UPDATER_ARTIFACT"
