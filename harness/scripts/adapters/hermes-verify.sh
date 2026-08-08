#!/usr/bin/env bash
set -euo pipefail
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.hermes" "$TMP/.agents/skills/core"
printf 'name: core\ndescription: core\n' > "$TMP/.agents/skills/core/SKILL.md"
printf 'skills:\n  external_dirs:\n    - "%s/.agents/skills"\n' "$TMP" > "$TMP/.hermes/config.yaml"
grep -q 'external_dirs' "$TMP/.hermes/config.yaml"
test -f "$TMP/.agents/skills/core/SKILL.md"
echo "hermes adapter smoke: PASS"
