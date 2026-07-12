#!/usr/bin/env bash
# harness-flow acceptance gate — รวม AgentMonitor + syntax check สคริปต์หลัก
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "=== harness-flow verify ==="

echo "== shell syntax check =="
for f in install.sh backup.sh scripts/*.sh agentmonitor/verify.sh; do
  [ -f "$f" ] && bash -n "$f"
done
for f in hermes/*.sh; do
  [ -f "$f" ] && bash -n "$f"
done

echo "== agentmonitor suite =="
bash agentmonitor/verify.sh

echo ""
echo "harness-flow verify: PASS"
