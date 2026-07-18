#!/usr/bin/env bash
# harness-flow acceptance — Agent Harness only (no AgentMonitor suite)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== harness-flow verify ==="

echo "== layout =="
test -f AGENTS.md
test -d skills
test -d memory
test -f memory/MEMORY.md
test -d standards
test -d scripts
test -x install.sh
test -f docs/AGENT_HARNESS.md
echo "layout: OK"

echo "== shell syntax =="
for f in install.sh backup.sh verify.sh bootstrap.sh scripts/*; do
  [ -f "$f" ] || continue
  case "$f" in
    *.py) continue ;;
  esac
  bash -n "$f"
done
echo "syntax: OK"

echo "== skills =="
count=$(find skills -mindepth 1 -maxdepth 1 ! -name '.*' | wc -l | tr -d ' ')
test "$count" -gt 0
echo "skills: $count"

echo "== memory =="
mcount=$(find memory -mindepth 1 -maxdepth 1 -name '*.md' ! -name '.*' | wc -l | tr -d ' ')
test "$mcount" -gt 0
echo "memory: $mcount md"

echo "== project wiki template (optional) =="
if [ -f templates/project-wiki/init-wiki.sh ]; then
  bash -n templates/project-wiki/init-wiki.sh
  echo "project-wiki template: OK"
fi

echo "== bootstrap / install-and-go =="
test -x bootstrap.sh
test -f adapters/CLAUDE.md
test -f adapters/claude-settings.defaults.json
test -f scripts/merge-claude-settings.py
python3 -c "import ast, pathlib; ast.parse(pathlib.Path('scripts/merge-claude-settings.py').read_text())"
grep -q 'harness update' scripts/harness
echo "bootstrap assets: OK"

echo ""
echo "harness-flow verify: PASS"
echo "On a machine after install, also run: harness doctor"

