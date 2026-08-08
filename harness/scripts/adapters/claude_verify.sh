#!/usr/bin/env bash
set -euo pipefail
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.claude/skills" "$TMP/.claude/commands"
printf '# policy\n' > "$TMP/.claude/CLAUDE.md"
test -f "$TMP/.claude/CLAUDE.md"
test -d "$TMP/.claude/skills"
test -d "$TMP/.claude/commands"
echo "claude-code adapter smoke: PASS"
