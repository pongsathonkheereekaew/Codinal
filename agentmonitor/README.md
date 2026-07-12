# AgentMonitor — pixel office สำหรับทีม AI (Hermes + Cursor)

ศูนย์มอนิเตอร์ + สั่งงาน + อนุมัติ merge ที่รันในเครื่องคุณเอง — Hermes เป็นผู้จัดการแตกงานให้ Cursor Cloud Agents ทำ ส่วนแอพนี้เป็น "ออฟฟิศ pixel" ให้เห็นว่าใครทำอะไรอยู่ห้องไหน พร้อม hard gate ที่บังคับให้ `./verify.sh` เขียวก่อน merge เสมอ

```
คุณ ── Telegram (พิมพ์สั่ง) ─────► Hermes Gateway (ผู้จัดการ — แตก 1–3 subtasks)
 │                                   │ launch + poll ลูกทีม → รวมผล → สรุปกลับ Telegram
 │                                   │ POST event → bridge ทุก transition
 │                                   ▼
 │                          Cursor Cloud Agents (คนงาน) ──► git + PR + ./verify.sh (truth)
 │
 └── เกม/แดชบอร์ด ◄─ WebSocket ─ TownHall bridge (Node + SQLite — เครื่องนี้เท่านั้น)
        │                            ├─ poll Cursor API = ground truth
        │                            ├─ hard gate: approve ได้เฉพาะ verify เขียว
        └─ กด Approve ──────────────►└─ followup ตรงเข้า Cursor agent (ไม่ผ่าน LLM)
```

## ห้องในออฟฟิศ (state จริง ไม่ใช่ animation ล้วน)

| ห้อง | ตัวละครอยู่เมื่อ |
|---|---|
| 🚪 Lobby | ว่างงาน / งานเพิ่งเข้าคิว (+โต๊ะ Manager = สถานะ Hermes) |
| 🌐 Crawl | stage research/อ่าน docs |
| 🔨 Build | กำลังเขียนโค้ด (Cursor `RUNNING`) |
| 🧪 Test | รัน `./verify.sh` — เขียว/แดงเห็นที่ chip |
| 👑 Boss Office | verify เขียว + PR เปิด → รอคุณกด Approve/Reject |
| ☕ Break | stalled (เงียบ >10 นาที) / paused (เกิน 45 นาที) / failed |
| 🖥 Server | สุขภาพระบบ (hermes · 9router · cursor api) |
| 🗄 Archive | mission ที่จบแล้ว |

## Quickstart (Mac)

```bash
cd agentmonitor/bridge
cp .env.example .env        # เติม CURSOR_API_KEY + TELEGRAM_BOT_TOKEN (+chmod 600 .env)
npm install
npm start                   # → http://127.0.0.1:4777
```

ฝั่ง Hermes: กติกา "Mission protocol" ถูกเพิ่มใน `harness-flow/hermes/SOUL.md` แล้ว —
รัน `hermes/install.sh` ใหม่หนึ่งครั้งเพื่อ deploy ไปยัง gateway จากนั้นพิมพ์สั่งงานใน Telegram ตามปกติ
ตัวละครจะโผล่ในออฟฟิศเอง (payload ตัวอย่างทุก event: `hermes/EVENTS.md`)

รันถาวรบน boot: `scripts/com.agentmonitor.bridge.plist` (แก้ `{{AGENTMONITOR_DIR}}`/`{{HOME}}` ก่อน)

## สั่งงานจากเกม → Hermes (Intake 3 โหมด)

ข้อจำกัดของ Telegram: บอทไม่เห็นข้อความจากบอทด้วยกัน — เกมจึงส่งเข้า bot ของ Hermes ตรงๆ ไม่ได้ ต้องเลือกโหมด:

| โหมด | วิธี | สถานะ |
|---|---|---|
| **A — hermes CLI** | รัน `scripts/spike-hermes-cli.sh` หา syntax แล้วตั้ง `HERMES_SEND_CMD` | สะอาดสุด — spike ก่อน |
| **B — MTProto user session** | `npm i telegram` + `node scripts/tg-login.mjs` → ส่ง "ในนามบัญชีคุณ" — Hermes เห็นเหมือนพิมพ์เอง ประวัติครบใน Telegram | ทำงานแน่นอน |
| **C — notify only** | bot `sendMessage` (token เดิมของ Hermes ใช้ได้ — bridge ไม่ polling จึงไม่ชน) | แจ้งเตือนอย่างเดียว |

`INTAKE_MODE=auto` จะลอง A ก่อนแล้วค่อย B — ยังไม่ config ทั้งคู่ก็ยังใช้แอพเป็น monitor + approve ได้เต็มรูปแบบ (สั่งงานผ่าน Telegram ตามเดิม) ทุกข้อความจากเกมมี prefix `🎮 [game]` ให้แยกออกในประวัติและให้ SOUL dedup ได้

## กติกาที่ระบบบังคับ (จาก grill session)

| กติกา | ค่า | บังคับที่ |
|---|---|---|
| merge ต้องบอส approve | ทุก mission | bridge → followup ตรงเข้า Cursor |
| verify แดงห้าม merge | hard gate — ไม่มี flag ข้าม | `POST /api/approve` → 409 `REJECTED_BY_GATE` |
| subtask ต่อ mission | ≤ 3 | `mission.created` → 400, `task.assigned` → 409 |
| เงียบเกิน 10 นาที | → stalled + แจ้ง Telegram | timers |
| เกิน 45 นาที | → auto pause + followup ให้ agent หยุด + ถามบอส | timers |
| เครื่องดับ/หลับ | บูตกลับมา → แจ้ง Telegram พร้อมจำนวนงานค้าง | health bootCheck |
| ลบตัวละคร (session) ได้ | memory หาย — git ยังเป็น truth | `POST /api/characters/:id/archive` |
| 🔒 local-only ต่อตัวละคร | Hermes ห้ามส่งขึ้น Cursor Cloud (SOUL ข้อ 8) | bridge block `task.assigned` → `LOCAL_ONLY_VIOLATION` |

## API (เกม Phaser ใน Phase 1 ใช้ชุดเดียวกันนี้)

| Endpoint | ใช้ทำอะไร |
|---|---|
| `GET /api/state` | snapshot ทั้งออฟฟิศ (characters/missions/tasks+room/approvals/health/events) |
| `WS /ws` | push `state.sync` ทุกการเปลี่ยนแปลง |
| `POST /api/events` | event sink จาก Hermes (ดู `hermes/EVENTS.md`) |
| `POST /api/approve` | `{approval_id \| task_id, decision: approved\|rejected, note}` |
| `POST /api/command` | `{text, topic, character}` → intake โหมด A/B |
| `POST /api/missions/:id/resume` / `cancel` | ปุ่ม Continue / ยกเลิก |
| `POST /api/restart-gateway` | รัน `harness-flow/hermes/restart-gateway.sh` |
| `GET /api/events?limit=100` | ไล่ debug โปรโตคอลฝั่ง Hermes |

Bind `127.0.0.1` โดย default — จะเปิดให้มือถือ (PWA ผ่าน Tailscale) ค่อยเปลี่ยน `BIND` + ตั้ง `API_TOKEN` (dashboard จะถาม token ครั้งแรกและเก็บใน localStorage)

**Verify truth ที่สอง:** ตั้ง `GITHUB_TOKEN` แล้ว poller จะเช็ค CI บน PR — ถ้า Hermes รายงาน verify เขียวแต่ GitHub CI แดง bridge จะ downgrade เป็นแดงอัตโนมัติ

## ทดสอบ

```bash
./verify.sh    # syntax check + test suite 15 ข้อ (rooms, meter, hard gate, spawn cap, local-only, CI override, E2E flow)
```

## แผนตาม gate 7 วัน (ตกลงกันไว้: bridge + status จริง + verify gate + Telegram แจ้ง = 4/4 ไปต่อ)

- [x] Bridge + events API + SQLite + dashboard สด (WS)
- [x] Verify hard gate + approve/reject → followup
- [x] Telegram แจ้งเตือน (stalled / pause / gateway down / เครื่องดับ)
- [ ] Day 1–2 บนเครื่องจริง: เติม `.env` + spike โหมด A + งาน ES-* จริง 1 ชิ้น E2E
- [ ] ครบ 4/4 → **Phase 1**: fork [agent-town](https://github.com/geezerrrr/agent-town) เปลี่ยน backend เป็น bridge นี้ (ดู `game/README.md`)
- [ ] **Phase 2**: PWA มือถือผ่าน Tailscale (ดู `pwa/README.md`)
- [ ] **Phase 3**: ห้อง 🔒 Insurance (local Claude Code), email intake, Archive เดินดูได้

## แยกออกเป็น repo ใหม่

สร้าง repo เปล่าบน GitHub ก่อน (ไม่ต้องมี README) แล้ว:

```bash
bash agentmonitor/scripts/extract-repo.sh git@github.com:USER/agentmonitor.git
```

## Security notes

- `.env` และ `TG_USER_SESSION` = สิทธิ์สูง — อยู่ใน `.gitignore` แล้ว, `chmod 600`, ห้ามออกจากเครื่อง
- bridge ออกแบบเป็น local-first: DB, event log, การตัดสิน gate อยู่บนเครื่องทั้งหมด
- งานที่ส่งขึ้น Cursor Cloud = โค้ดออกจากเครื่อง (repo private) — งาน insurance ใช้ 🔒 local-only ตามนโยบาย
