#!/usr/bin/env bash
# รัน bridge โหมด dev (auto-reload) — เปิด dashboard ที่ http://127.0.0.1:4777
set -euo pipefail
cd "$(dirname "$0")/../bridge"
[ -d node_modules ] || npm install --no-fund --no-audit
[ -f .env ] || { cp .env.example .env; echo "สร้าง .env จาก example แล้ว — เติมค่าก่อนใช้จริง"; }
exec node --watch src/index.js
