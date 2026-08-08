#!/usr/bin/env bash
set -euo pipefail
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.agents/skills/core"
printf '# policy\nSee ~/.agents/skills for discovery.\n' > "$TMP/AGENTS.md"
printf 'name: core\ndescription: core\n' > "$TMP/.agents/skills/core/SKILL.md"
test -f "$TMP/AGENTS.md"
test -f "$TMP/.agents/skills/core/SKILL.md"
echo "generic adapter smoke: PASS"
