# Phase 2 — companion มือถือ (PWA)

หลัง Phase 1 — มือถือเป็น remote UI ของ bridge บน Mac (agent ทั้งหมดยังรันบน Mac)

## แนวทาง

- การ์ดตัวละคร + สถานะ + meter + ปุ่ม Approve/Reject — ไม่ต้องมี pixel map เต็ม (ลากบนมือถือไม่ลื่น)
- เข้าถึงผ่าน **Tailscale**: ตั้ง `BIND=<tailscale-ip>` + `API_TOKEN=<random>` ใน bridge/.env
  แล้วเปิด `http://<mac-tailscale-name>:4777` จากมือถือ (ใส่ token)
- แจ้งเตือนหลักยังเป็น Telegram (โหมด C) — PWA ไม่ต้องทำ push เอง
- สั่งงานจากมือถือ: พิมพ์ Telegram ตรงเหมือนเดิมเร็วกว่า — ช่อง command ใน PWA เป็น optional
