# Phase 1 — เกม pixel office (Phaser)

เริ่มเมื่อผ่าน gate 7 วัน (bridge + status จริง + verify gate + Telegram แจ้ง ครบ 4/4)

## แนวทาง: fork ไม่เขียนใหม่

1. Fork [geezerrrr/agent-town](https://github.com/geezerrrr/agent-town) (Phaser office + React HUD)
2. จุดผ่าตัดหลักจุดเดียว: เปลี่ยน WebSocket layer จาก OpenClaw gateway → **TownHall bridge**
   - subscribe `ws://127.0.0.1:4777/ws` → รับ `state.sync` ทั้งก้อน
   - task.room ← bridge คำนวณให้แล้ว (`server/crawl/test/break/build/archive/lobby/boss`)
   - sprite เดินไปห้องใหม่เมื่อ room เปลี่ยน — ไม่ต้องมี logic เอง
3. ปุ่ม/interaction map เข้า REST เดิม: approve/reject → `POST /api/approve`, สั่งงาน → `POST /api/command`,
   Continue/ยกเลิก → `/api/missions/:id/resume|cancel`
4. Manager sprite (Hermes) ที่โต๊ะหน้า Lobby — เดิน brief เมื่อมี `mission.created`, เก็บรายงานเมื่อ `mission.report`

## Acceptance

เท่ากับ dashboard v0 ทุกข้อ แต่เดินดูได้ — ห้ามมี state ในเกมที่ไม่ได้มาจาก bridge
(กัน "sprite นั่งทำงานทั้งที่ gateway ตายไปแล้ว")
