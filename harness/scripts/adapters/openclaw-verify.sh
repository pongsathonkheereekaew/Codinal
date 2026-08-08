#!/usr/bin/env bash
set -euo pipefail
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.openclaw/skills/core"
printf 'name: core\ndescription: core\n' > "$TMP/.openclaw/skills/core/SKILL.md"
test -f "$TMP/.openclaw/skills/core/SKILL.md"
echo "openclaw adapter smoke: PASS"
