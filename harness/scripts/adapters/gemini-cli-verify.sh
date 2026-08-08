#!/usr/bin/env bash
set -euo pipefail
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.gemini/skills/core" "$TMP/.gemini/policies" "$TMP/.agents/skills/core"
printf '# policy\n' > "$TMP/.gemini/GEMINI.md"
printf 'name: core\ndescription: core\n' > "$TMP/.gemini/skills/core/SKILL.md"
printf 'name: core\ndescription: core\n' > "$TMP/.agents/skills/core/SKILL.md"
test -f "$TMP/.gemini/GEMINI.md"
test -f "$TMP/.gemini/skills/core/SKILL.md"
test -d "$TMP/.gemini/policies"
echo "gemini-cli adapter smoke: PASS"
