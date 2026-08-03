#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
BUNDLE_ROOT="${1:-$ROOT/desktop/gpui/target/release/bundle}"
APP="${2:-$BUNDLE_ROOT/macos/Codinal.app}"

test -d "$APP"
test -x "$APP/Contents/MacOS/codinal"
test -x "$APP/Contents/Resources/codinal-runtime"

file_size() {
  if stat -f '%z' "$1" >/dev/null 2>&1; then
    stat -f '%z' "$1"
  else
    stat -c '%s' "$1"
  fi
}

tree_size() {
  local path="$1"
  if [ ! -e "$path" ]; then
    printf '%s' "unknown"
    return
  fi
  find "$path" -type f -print0 \
    | while IFS= read -r -d '' file; do file_size "$file"; done \
    | awk '{ total += $1 } END { print total + 0 }'
}

debug_symbols_size() {
  local total=0
  local found=0
  local path
  while IFS= read -r -d '' path; do
    found=1
    total=$((total + $(tree_size "$path")))
  done < <(find "$BUNDLE_ROOT" -type d -name '*.dSYM' -print0)
  if [ "$found" -eq 0 ]; then
    printf '%s' "0"
  else
    printf '%s' "$total"
  fi
}

emit() {
  printf '%s\t%s\n' "$1" "$2"
}

emit metric bytes
emit native_gpui_bytes "$(file_size "$APP/Contents/MacOS/codinal")"
emit native_runtime_bytes "$(file_size "$APP/Contents/Resources/codinal-runtime")"
emit app_bundle_bytes "$(tree_size "$APP")"
emit sbom_bytes "$(file_size "$APP/Contents/Resources/Codinal-rust-sbom.json")"
emit editor_bundle_target_bytes 892815
emit legacy_editor_source_bytes "$(tree_size "$ROOT/desktop/ui")"
emit editor_bundle_raw_bytes "$(tree_size "$ROOT/desktop/ui/dist")"
emit archive_zip_bytes "$(tree_size "$BUNDLE_ROOT"/*-macos-arm64.zip)"
emit archive_tar_gz_bytes "$(tree_size "$BUNDLE_ROOT"/*-macos-arm64.app.tar.gz)"
emit debug_symbols_bytes "$(debug_symbols_size)"
