#!/usr/bin/env bash
set -euo pipefail
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.zcode/skills/core" "$TMP/.zcode/commands"
printf '# policy\n' > "$TMP/.zcode/AGENTS.md"
printf 'name: core\ndescription: core\n' > "$TMP/.zcode/skills/core/SKILL.md"
printf '#!/bin/sh\n' > "$TMP/.zcode/commands/status.md"
test -f "$TMP/.zcode/AGENTS.md"
test -f "$TMP/.zcode/skills/core/SKILL.md"
test -d "$TMP/.zcode/commands"
echo "zcode adapter smoke: PASS"
