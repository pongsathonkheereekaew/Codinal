#!/usr/bin/env bash
# harness-flow acceptance gate
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== harness-flow verify ==="

echo "== shell syntax check =="
for f in install.sh backup.sh \
  scripts/*.sh \
  agentmonitor/verify.sh \
  templates/agents-harness/install.sh \
  templates/project-wiki/init-wiki.sh; do
  [ -f "$f" ] && bash -n "$f"
done
for f in hermes/*.sh; do
  [ -f "$f" ] && bash -n "$f"
done
for f in templates/agents-harness/scripts/*; do
  [ -f "$f" ] && bash -n "$f"
done

echo "== agent harness template =="
test -f docs/AGENT_HARNESS.md
test -f templates/agents-harness/AGENTS.md
test -f templates/agents-harness/install.sh
test -f templates/agents-harness/scripts/harness
echo "agent harness template: OK"

echo "== project wiki scaffold =="
test -f docs/wiki/SCHEMA.md
test -f docs/wiki/index.md
test -f docs/wiki/log.md
test -f .cursor/rules/project-wiki.mdc
test -f templates/project-wiki/init-wiki.sh
test -f templates/project-wiki/SCHEMA.md
echo "project wiki: OK"

echo "== agentmonitor suite =="
bash agentmonitor/verify.sh

echo ""
echo "harness-flow verify: PASS"
