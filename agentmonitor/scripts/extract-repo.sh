#!/usr/bin/env bash
# แยก agentmonitor/ ออกเป็น repo ใหม่ (รันบน Mac ครั้งเดียว)
# ขั้นตอนก่อนรัน: สร้าง repo เปล่าบน GitHub (ห้ามติ๊ก README/gitignore) เช่น agentmonitor
# ใช้: bash agentmonitor/scripts/extract-repo.sh git@github.com:USER/agentmonitor.git
set -euo pipefail

NEW_REMOTE=${1:?usage: extract-repo.sh git@github.com:USER/agentmonitor.git}
ROOT=$(git rev-parse --show-toplevel)
cd "$ROOT"

echo "== แยกประวัติเฉพาะ agentmonitor/ ด้วย git subtree =="
git subtree split -P agentmonitor -b agentmonitor-export

TMP=$(mktemp -d)
git clone -q . -b agentmonitor-export "$TMP/agentmonitor"
cd "$TMP/agentmonitor"
git remote set-url origin "$NEW_REMOTE"
git push -u origin agentmonitor-export:main

echo ""
echo "✅ done → $NEW_REMOTE (branch main)"
echo "ลบ branch ชั่วคราวใน harness-flow ได้ด้วย: git branch -D agentmonitor-export"
echo "จากนั้นจะลบโฟลเดอร์ agentmonitor/ ใน harness-flow หรือเก็บไว้ sync ต่อก็ได้ (เลือกอย่างใดอย่างหนึ่งเพื่อกัน drift)"
