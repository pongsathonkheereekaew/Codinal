#!/usr/bin/env bash
set -euo pipefail
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.cursor/rules" "$TMP/.cursor/skills/core" "$TMP/.cursor/commands"
printf -- '---\nalwaysApply: true\n---\n# agents policy\n' > "$TMP/.cursor/rules/agents-policy.mdc"
printf 'name: core\ndescription: core\n' > "$TMP/.cursor/skills/core/SKILL.md"
test -f "$TMP/.cursor/rules/agents-policy.mdc"
grep -q 'alwaysApply: true' "$TMP/.cursor/rules/agents-policy.mdc"
test -f "$TMP/.cursor/skills/core/SKILL.md"
test -d "$TMP/.cursor/commands"
echo "cursor adapter smoke: PASS"
