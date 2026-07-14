#!/usr/bin/env bash
# harness-flow acceptance — Agent Harness only (no AgentMonitor suite)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== harness-flow verify ==="

echo "== layout =="
test -f AGENTS.md
test -d skills
test -d standards
test -d scripts
test -x install.sh
test -f docs/AGENT_HARNESS.md
echo "layout: OK"

echo "== shell syntax =="
for f in install.sh backup.sh verify.sh scripts/*; do
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

echo "== project wiki template (optional) =="
if [ -f templates/project-wiki/init-wiki.sh ]; then
  bash -n templates/project-wiki/init-wiki.sh
  echo "project-wiki template: OK"
fi

echo ""
echo "harness-flow verify: PASS"
