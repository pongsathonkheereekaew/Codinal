#!/usr/bin/env bash
# AgentMonitor acceptance gate — ต้อง exit 0 ก่อนถือว่างานเสร็จ (กติกาเดียวกับ Easby)
set -euo pipefail
cd "$(dirname "$0")/bridge"

if [ ! -d node_modules ]; then
  echo "== installing bridge deps =="
  npm install --no-fund --no-audit
fi

echo "== syntax check =="
for f in src/*.js src/intake/*.js; do node --check "$f"; done

echo "== test suite =="
npm test

echo ""
echo "AgentMonitor verify: PASS"
