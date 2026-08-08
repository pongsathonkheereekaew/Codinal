#!/usr/bin/env bash
set -euo pipefail
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.codex" "$TMP/.agents/skills/core"
printf '# policy\n' > "$TMP/.codex/AGENTS.md"
printf 'name: core\ndescription: core\n' > "$TMP/.agents/skills/core/SKILL.md"
test -f "$TMP/.codex/AGENTS.md"
test -f "$TMP/.agents/skills/core/SKILL.md"
echo "codex adapter smoke: PASS"
