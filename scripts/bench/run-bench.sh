#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="$ROOT/docs/evidence/market/a2"
mkdir -p "$OUT"
for agent in cedia opencode; do
  node --experimental-strip-types "$ROOT/scripts/bench/report.ts" \
    --agent "$agent" \
    --cases "$ROOT/harness/eval/cases/market-bench.json" \
    --out "$OUT/$agent.json"
done
python3 - "$OUT" <<'PY'
import json, pathlib, sys
for p in pathlib.Path(sys.argv[1]).glob("*.json"):
    data = json.loads(p.read_text())
    assert {"agent","cases"} <= set(data), p
PY
echo "bench: OK"
