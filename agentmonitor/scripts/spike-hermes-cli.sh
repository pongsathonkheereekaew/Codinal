#!/usr/bin/env bash
# Day-1 spike — โหมด A: hermes CLI ส่งข้อความเข้า session ได้ไหม?
# ถ้าได้ → สั่งงานจากเกมโดยไม่ต้องแตะบัญชี Telegram เลย (สะอาดสุด)
set -uo pipefail
HB=${HERMES_BIN:-hermes}

if ! command -v "$HB" >/dev/null 2>&1; then
  echo "❌ hermes ไม่อยู่บน PATH — ติดตั้งก่อน (ดู harness-flow/NEW_MACHINE.md)"
  exit 1
fi

echo "== hermes --help | คำที่เกี่ยวกับการส่งข้อความ =="
"$HB" --help 2>&1 | grep -inE "send|chat|message|inject|session|gateway" || echo "(ไม่พบที่ระดับบนสุด)"

for sub in send chat message gateway session sessions agent; do
  echo ""
  echo "== hermes $sub --help =="
  "$HB" "$sub" --help 2>&1 | head -15
done

cat <<'EOF'

── ผลการ spike ──────────────────────────────────────────────
พบคำสั่งส่งข้อความเข้า session/topic ได้:
  → ตั้งใน bridge/.env เช่น
    HERMES_SEND_CMD=hermes send --chat {chat} --topic {topic} --text "$AM_TEXT"
    ($AM_TEXT / $AM_TOPIC / $AM_CHAT ถูก inject เป็น env — ปลอดภัยเรื่อง quoting)

ไม่พบ:
  → ใช้โหมด B (ส่งในนามบัญชีคุณผ่าน MTProto):
    cd bridge && npm i telegram && node ../scripts/tg-login.mjs
    แล้วเติม TG_API_ID / TG_API_HASH / TG_USER_SESSION ใน .env
─────────────────────────────────────────────────────────────
EOF
